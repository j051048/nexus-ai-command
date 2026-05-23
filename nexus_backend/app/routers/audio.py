"""
Audio transcription endpoint.
Accepts audio file upload and returns transcribed text using STT model.
WebM files are transcoded to MP3 before sending to upstream STT providers,
because many proxy gateways (One-API/New-API) cannot parse streaming WebM
duration metadata for billing.
"""

import asyncio
import contextlib
import logging
import os
import shutil
import subprocess
import tempfile

from fastapi import APIRouter, Depends, File, Request, UploadFile
from openai import AsyncOpenAI

from app.core.auth import get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audio", tags=["Audio"])

ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/mp4",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/x-m4a",
    "audio/m4a",
    "video/webm",  # Android Chrome MediaRecorder sometimes outputs this
}

MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25MB (OpenAI limit)

MIME_TO_EXT = {
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/ogg": ".ogg",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
}

# Formats that need transcoding before sending to upstream proxy gateways.
# WebM (streaming EBML) lacks duration metadata, causing billing modules to crash.
NEEDS_TRANSCODE = {".webm", ".ogg"}

# Check ffmpeg availability at module load
_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


async def _transcode_to_mp3(input_path: str) -> str | None:
    """Transcode audio file to MP3 using ffmpeg. Returns new path or None on failure."""
    output_path = input_path.rsplit(".", 1)[0] + ".mp3"
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i",
            input_path,
            "-y",  # overwrite
            "-vn",  # no video
            "-acodec",
            "libmp3lame",
            "-ab",
            "64k",  # 64kbps is enough for speech
            "-ar",
            "16000",  # 16kHz sample rate for speech
            "-ac",
            "1",  # mono
            output_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            logger.warning(
                f"[Audio] ffmpeg transcode failed (rc={proc.returncode}): {stderr.decode(errors='ignore')[:200]}"
            )
            return None
        logger.info(
            f"[Audio] Transcoded {input_path} -> {output_path} ({os.path.getsize(output_path)} bytes)"
        )
        return output_path
    except TimeoutError:
        logger.warning("[Audio] ffmpeg transcode timed out (30s)")
        return None
    except Exception as e:
        logger.warning(f"[Audio] ffmpeg transcode error: {e}")
        return None


# Models to try in order: primary -> fallback
STT_MODELS = ["gpt-4o-mini-transcribe", "gpt-4o-transcribe"]


async def _get_ai_config(req: Request, user_id: str) -> dict:
    """Load user AI config (base_url + api_key), same logic as chat.py."""
    ai_config = {
        "base_url": os.getenv("AI_BASE_URL", "https://proxy.flydao.top/v1"),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
    }

    try:
        client = get_request_db(req)
        org_id = getattr(req.state, "org_id", None)
        settings_query = client.table("ai_settings").select("*").eq("user_id", user_id)
        if org_id:
            settings_query = settings_query.eq("organization_id", org_id)
        settings_res = await settings_query.maybe_single().execute()

        if settings_res.data:
            s = settings_res.data
            from app.services.encryption_service import encryption_service

            if s.get("base_url"):
                user_base_url = s["base_url"].rstrip("/")
                if user_base_url.endswith("/chat/completions"):
                    user_base_url = user_base_url[: -len("/chat/completions")]
                ai_config["base_url"] = user_base_url
            if s.get("api_key"):
                try:
                    ai_config["api_key"] = encryption_service.decrypt(s["api_key"])
                except Exception:
                    logger.warning("API key decryption failed for audio transcribe")
                    ai_config["api_key"] = ""
    except Exception as e:
        logger.warning(f"AI settings fetch failed for audio: {e}")

    return ai_config


async def _try_transcribe(
    openai_client: AsyncOpenAI, tmp_path: str, model: str
) -> str | None:
    """Attempt transcription with a specific model. Returns text or None on failure."""
    try:
        with open(tmp_path, "rb") as audio_file:
            transcript = await openai_client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                language="zh",
            )
        return transcript.text.strip()
    except Exception as e:
        error_str = str(e)
        # Check if it's a rate limit (429), service unavailable (503/500), or model not found error
        if (
            "429" in error_str
            or "503" in error_str
            or "500" in error_str
            or "rate" in error_str.lower()
            or "负载" in error_str
            or "无可用渠道" in error_str
            or "count_token_failed" in error_str.lower()
        ):
            logger.warning(
                f"[Audio] Model {model} unavailable/rate-limited, will try fallback"
            )
            return None
        if (
            "404" in error_str
            or "not found" in error_str.lower()
            or "does not exist" in error_str.lower()
        ):
            logger.warning(f"[Audio] Model {model} not available, will try fallback")
            return None
        # Other errors: re-raise
        raise


@router.post("/transcribe")
async def transcribe_audio(
    req: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """语音转文字端点。接受音频文件，返回转写文本。"""
    # 1. Validate audio type (strip codec params like ";codecs=opus")
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_FORMAT,
            f"不支持的音频格式: {content_type}",
        )

    # 2. Read and validate size
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise api_error(
            ErrorCode.VALIDATION_VALUE_OUT_OF_RANGE,
            f"音频文件过大 ({len(audio_bytes) // 1024 // 1024}MB)，最大 25MB",
        )
    if len(audio_bytes) < 100:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            "音频文件太小，可能未录到声音",
        )

    # 3. Load user AI config
    get_request_db(req)
    ai_config = await _get_ai_config(req, user_id)
    if not ai_config["api_key"]:
        raise api_error(
            ErrorCode.AI_SERVICE_UNAVAILABLE,
            "未配置 AI API Key，无法进行语音转写",
        )

    # 4. Write to temp file, transcode if needed, then call STT with fallback
    ext = MIME_TO_EXT.get(content_type, ".webm")
    tmp_path = None
    transcoded_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # Transcode webm/ogg to mp3 to avoid upstream proxy billing parse failures
        stt_path = tmp_path
        if ext in NEEDS_TRANSCODE and _FFMPEG_AVAILABLE:
            logger.info(f"[Audio] Transcoding {ext} -> mp3 for proxy compatibility")
            transcoded_path = await _transcode_to_mp3(tmp_path)
            if transcoded_path:
                stt_path = transcoded_path
            else:
                logger.warning("[Audio] Transcode failed, sending original file")
        elif ext in NEEDS_TRANSCODE:
            logger.warning("[Audio] ffmpeg not available, sending original webm/ogg")

        base_url = ai_config["base_url"]
        # Ensure base_url ends with /v1 for OpenAI-compatible APIs
        if not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        logger.info(
            f"[Audio] Calling STT: base_url={base_url}, "
            f"audio_size={len(audio_bytes)}, mime={content_type}, "
            f"stt_file={stt_path}, user={user_id}"
        )

        openai_client = AsyncOpenAI(
            api_key=ai_config["api_key"],
            base_url=base_url,
            max_retries=3,
        )

        # Try each model in order until one succeeds
        text = None
        last_error = None
        for model in STT_MODELS:
            try:
                result = await _try_transcribe(openai_client, stt_path, model)
                if result is not None:
                    text = result
                    logger.info(f"[Audio] Model {model} succeeded")
                    break
                # result is None means recoverable error, try next model
            except Exception as e:
                last_error = e
                logger.warning(f"[Audio] Model {model} failed: {e}")
                continue

        if text is None and last_error:
            raise last_error
        if text is None:
            raise api_error(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "语音识别服务暂时繁忙，请稍后再试",
            )

        if not text:
            return api_success(
                data={"text": "", "empty": True},
                message="未识别到语音内容",
            )

        logger.info(
            f"[Audio] Transcribed {len(audio_bytes)} bytes -> {len(text)} chars for user={user_id}"
        )
        return api_success(data={"text": text})

    except Exception as e:
        error_str = str(e)
        logger.error(f"[Audio] Transcription failed for user={user_id}: {e}")

        # User-friendly error messages
        if (
            "429" in error_str
            or "503" in error_str
            or "500" in error_str
            or "rate" in error_str.lower()
            or "负载" in error_str
            or "无可用渠道" in error_str
            or "count_token_failed" in error_str.lower()
        ):
            raise api_error(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "语音识别服务繁忙，请等几秒后再试",
            )
        if "401" in error_str or "auth" in error_str.lower():
            raise api_error(
                ErrorCode.AI_SERVICE_UNAVAILABLE,
                "AI API Key 无效，请检查设置",
            )

        raise api_error(
            ErrorCode.AI_SERVICE_UNAVAILABLE,
            f"语音转写失败: {error_str[:80]}",
        )
    finally:
        for path in (tmp_path, transcoded_path):
            if path:
                with contextlib.suppress(Exception):
                    os.unlink(path)

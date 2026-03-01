"""
Audio transcription endpoint.
Accepts audio file upload and returns transcribed text using STT model.
"""

import contextlib
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Request, UploadFile
from openai import AsyncOpenAI

from app.core.auth import get_current_user_id
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


async def _get_ai_config(req: Request, user_id: str) -> dict:
    """Load user AI config (base_url + api_key), same logic as chat.py."""
    ai_config = {
        "base_url": os.getenv("AI_BASE_URL", "https://proxy.flydao.top/v1"),
        "api_key": os.getenv("OPENAI_API_KEY", ""),
    }

    try:
        client = req.state.db
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
    ai_config = await _get_ai_config(req, user_id)
    if not ai_config["api_key"]:
        raise api_error(
            ErrorCode.AI_SERVICE_UNAVAILABLE,
            "未配置 AI API Key，无法进行语音转写",
        )

    # 4. Write to temp file and call STT
    ext = MIME_TO_EXT.get(content_type, ".webm")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        base_url = ai_config["base_url"]
        # Ensure base_url ends with /v1 for OpenAI-compatible APIs
        if not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        logger.info(
            f"[Audio] Calling STT: base_url={base_url}, "
            f"audio_size={len(audio_bytes)}, mime={content_type}, user={user_id}"
        )

        openai_client = AsyncOpenAI(
            api_key=ai_config["api_key"],
            base_url=base_url,
        )

        with open(tmp_path, "rb") as audio_file:
            transcript = await openai_client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file,
                language="zh",
            )

        text = transcript.text.strip()
        if not text:
            return api_success(
                data={"text": "", "empty": True},
                message="未识别到语音内容",
            )

        logger.info(f"[Audio] Transcribed {len(audio_bytes)} bytes -> " f"{len(text)} chars for user={user_id}")
        return api_success(data={"text": text})

    except Exception as e:
        logger.error(f"[Audio] Transcription failed for user={user_id}: {e}")
        raise api_error(
            ErrorCode.AI_SERVICE_UNAVAILABLE,
            f"语音转写失败: {str(e)[:100]}",
        )
    finally:
        if tmp_path:
            with contextlib.suppress(Exception):
                os.unlink(tmp_path)

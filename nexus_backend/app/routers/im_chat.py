"""
IM 聊天消息通道 — 飞书/企微双向 AI 对话

接收飞书和企业微信的用户消息，路由到 AI Agent 处理，
然后将 AI 回复发送回 IM 平台。

支持的平台：
- 飞书 (Feishu/Lark): Event Subscription v2.0
- 企业微信 (WeCom): 接收消息回调

流程:
1. IM 平台将用户消息推送到 webhook
2. 验证签名 → 解析消息 → 查找/创建用户映射
3. 调用 AI Agent 获取回复（非流式）
4. 通过平台 API 将回复发送回用户
"""

import hashlib
import json
import logging

import httpx
from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.database import supabase
from app.core.errors import api_success
from app.agent.result_cache import _generate_cache_key
from app.core.cache import redis_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/im-chat", tags=["IM Chat Channel"])


# ═══════════════════════════════════════════════════════════════════════════════
#  飞书消息通道
# ═══════════════════════════════════════════════════════════════════════════════


async def _get_feishu_tenant_token() -> str | None:
    """获取飞书 tenant_access_token"""
    app_id = settings.FEISHU_APP_ID
    app_secret = settings.FEISHU_APP_SECRET
    if not app_id or not app_secret:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
            data = resp.json()
            if data.get("code") == 0:
                return data.get("tenant_access_token")
    except Exception as e:
        logger.error(f"Failed to get feishu tenant token: {e}")
    return None


async def _reply_feishu_message(message_id: str, content: str):
    """通过飞书 API 回复消息"""
    token = await _get_feishu_tenant_token()
    if not token:
        logger.error("Cannot reply feishu message: no tenant token")
        return

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(
                f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "content": f'{{"text": "{content}"}}',
                    "msg_type": "text",
                },
            )
    except Exception as e:
        logger.error(f"Failed to reply feishu message: {e}")


@router.post("/feishu/event")
async def feishu_event_handler(request: Request):
    """
    飞书事件订阅回调 — 接收用户发给机器人的消息

    配置步骤:
    1. 飞书开放平台 → 应用 → 事件订阅 → 请求地址: {your_domain}/api/im-chat/feishu/event
    2. 添加事件: im.message.receive_v1
    3. 权限: im:message, im:message:send_as_bot
    """
    body = await request.json()

    # URL 验证（首次配置回调时飞书发送 challenge）
    if "challenge" in body:
        return {"challenge": body["challenge"]}

    # 验证签名
    encrypt_key = settings.FEISHU_ENCRYPT_KEY
    if encrypt_key:
        timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = request.headers.get("X-Lark-Request-Nonce", "")
        signature = request.headers.get("X-Lark-Signature", "")
        body_bytes = await request.body()
        content = f"{timestamp}{nonce}{encrypt_key}".encode() + body_bytes
        expected = hashlib.sha256(content).hexdigest()
        if expected != signature:
            logger.warning("[im-chat] Invalid feishu signature")
            return {"code": 1, "msg": "invalid signature"}

    # 解析事件
    header = body.get("header", {})
    event = body.get("event", {})

    # 只处理 im.message.receive_v1 事件
    event_type = header.get("event_type", "")
    if event_type != "im.message.receive_v1":
        return api_success(data={"msg": "event ignored"})

    # 解析消息
    message = event.get("message", {})
    msg_type = message.get("message_type", "")
    message_id = message.get("message_id", "")
    chat_type = message.get("chat_type", "")  # p2p or group
    sender = event.get("sender", {}).get("sender_id", {})
    open_id = sender.get("open_id", "")

    # 只处理文本消息和私聊
    if msg_type != "text":
        await _reply_feishu_message(message_id, "目前只支持文本消息哦~")
        return api_success(data={"msg": "non-text ignored"})

    # 解析文本内容
    import json

    try:
        content_obj = json.loads(message.get("content", "{}"))
        user_text = content_obj.get("text", "").strip()
    except Exception:
        user_text = ""

    if not user_text:
        return api_success(data={"msg": "empty message"})

    # 群聊中需要 @机器人才响应
    if chat_type == "group" and not user_text.startswith("@"):
        return api_success(data={"msg": "not mentioned in group"})

    # 清理 @提及
    user_text = user_text.lstrip("@").strip()
    # 移除可能的机器人名称前缀
    for prefix in ["AI助手", "助手", "Nexus"]:
        if user_text.startswith(prefix):
            user_text = user_text[len(prefix) :].strip()
            break

    if not user_text:
        await _reply_feishu_message(message_id, "请问有什么可以帮您的？")
        return api_success(data={"msg": "empty after cleanup"})

    # 查找用户映射
    user_id = await _resolve_im_user("feishu", open_id)

    # 调用 AI Agent
    ai_reply = await _call_agent(user_id, user_text, f"feishu:{open_id}")

    # 回复消息
    await _reply_feishu_message(message_id, ai_reply)

    return api_success(data={"msg": "processed"})


# ═══════════════════════════════════════════════════════════════════════════════
#  企业微信消息通道
# ═══════════════════════════════════════════════════════════════════════════════


async def _reply_wecom_message(user_id: str, content: str):
    """通过企业微信 API 发送消息给用户"""
    corp_id = settings.WECOM_CORP_ID
    corp_secret = settings.WECOM_CORP_SECRET
    agent_id = settings.WECOM_AGENT_ID
    if not corp_id or not corp_secret or not agent_id:
        logger.error("Cannot reply wecom message: missing config")
        return

    try:
        # 获取 access_token
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.get(
                "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                params={"corpid": corp_id, "corpsecret": corp_secret},
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                logger.error(f"Failed to get wecom token: {token_data.get('errmsg')}")
                return

            # 发送消息
            await client.post(
                f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}",
                json={
                    "touser": user_id,
                    "msgtype": "text",
                    "agentid": int(agent_id),
                    "text": {"content": content},
                },
            )
    except Exception as e:
        logger.error(f"Failed to reply wecom message: {e}")


@router.post("/wecom/event")
async def wecom_event_handler(request: Request):
    """
    企业微信接收消息回调

    配置步骤:
    1. 企业微信管理后台 → 应用 → 接收消息 → URL: {your_domain}/api/im-chat/wecom/event
    2. 设置 Token 和 EncodingAESKey
    3. 开启接收消息功能
    """
    # 企微 URL 验证（GET 请求）
    if request.method == "GET":
        echostr = request.query_params.get("echostr", "")
        return echostr

    body = await request.json()

    # 解析消息
    msg_type = body.get("MsgType", "")
    from_user = body.get("FromUserName", "")
    content = body.get("Content", "").strip()

    if msg_type != "text" or not content:
        return ""

    # 查找用户映射
    user_id = await _resolve_im_user("wecom", from_user)

    # 调用 AI Agent
    ai_reply = await _call_agent(user_id, content, f"wecom:{from_user}")

    # 回复消息
    await _reply_wecom_message(from_user, ai_reply)

    return ""


# ═══════════════════════════════════════════════════════════════════════════════
#  共享辅助函数
# ═══════════════════════════════════════════════════════════════════════════════


async def _resolve_im_user(platform: str, platform_user_id: str) -> str:
    """
    将 IM 平台用户 ID 映射到 Nexus 用户 ID。
    如果映射不存在，返回一个基于平台的虚拟 ID。
    """
    if not supabase:
        return f"{platform}_{platform_user_id}"

    try:
        result = (
            await supabase.table("im_user_mappings")
            .select("user_id")
            .eq("platform", platform)
            .eq("platform_user_id", platform_user_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["user_id"]
    except Exception as e:
        logger.warning(f"Failed to resolve IM user mapping: {e}")

    return f"{platform}_{platform_user_id}"


async def _call_agent(user_id: str, message: str, session_id: str) -> str:
    """
    调用 AI Agent 获取非流式回复。
    用于 IM 消息通道，不需要流式输出。
    """
    import os

    try:
        from app.agent.graph import get_agent_graph
        from app.agent.memory import prepare_initial_state
        from app.agent.state import AgentConfig
        from app.services.chat_service import ChatService

        # 构建配置
        config = AgentConfig(
            user_id=user_id,
            session_id=session_id,
            api_key=os.getenv("OPENAI_API_KEY", settings.OPENAI_API_KEY),
            base_url=os.getenv("AI_BASE_URL", settings.AI_BASE_URL),
            model=settings.AI_DEFAULT_MODEL,
            mini_model=settings.AI_MINI_MODEL,
        )

        # 获取系统 prompt
        system_prompt = await ChatService.get_system_prompt("default")

        # 准备初始状态
        messages = [{"role": "user", "content": message}]
        initial_state = await prepare_initial_state(
            messages=messages,
            config=config,
            system_prompt=system_prompt,
        )

        # 检查缓存
        cache_key = _generate_cache_key(user_id, message, org_id=None)
        cached = redis_client.get(cache_key)
        if cached:
            cached_result = json.loads(cached)
            reply = cached_result.get("reply", "")
            logger.info(f"[IM Chat] Using cached agent result for user {user_id}")
        else:
            # 运行 Agent
            graph = get_agent_graph()
            final_state = await graph.run(initial_state, thread_id=session_id)

            # 提取回复
            reply = final_state.get("final_response", "")
            if not reply:
                # 从消息中提取最后一个 AI 回复
                for msg in reversed(final_state.get("messages", [])):
                    if hasattr(msg, "content") and hasattr(msg, "type") and msg.type == "ai":
                        reply = msg.content
                        break

            # 缓存结果
            try:
                redis_client.setex(cache_key, 1800, json.dumps({"reply": reply}, ensure_ascii=False))
            except Exception as e:
                logger.warning(f"Failed to cache agent result: {e}")

        # 保存消息
        try:
            await ChatService.save_message(user_id, session_id, "user", message)
            if reply:
                await ChatService.save_message(user_id, session_id, "assistant", reply)
        except Exception:
            pass

        return reply or "抱歉，我暂时无法回复。请稍后再试。"

    except Exception as e:
        logger.error(f"IM agent call failed: {e}", exc_info=True)
        return "系统处理异常，请稍后再试。"

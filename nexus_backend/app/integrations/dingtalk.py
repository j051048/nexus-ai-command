"""钉钉集成"""
import logging
import httpx

logger = logging.getLogger(__name__)

async def send_dingtalk_notification(webhook: str, message: str):
    """发送钉钉通知"""
    if not webhook:
        logger.warning("钉钉webhook未配置")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook,
                json={"msgtype": "text", "text": {"content": message}},
                timeout=5.0
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"发送钉钉通知失败: {e}")
        return False

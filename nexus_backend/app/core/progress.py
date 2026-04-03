"""
简单进度反馈 - 通过 WebSocket 推送进度消息
"""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class ProgressHelper:
    """进度反馈辅助类"""

    def __init__(self, callback: Callable | None = None):
        """
        Args:
            callback: WebSocket 发送函数，签名为 async def send(message: str)
        """
        self.callback = callback

    async def send(self, message: str):
        """发送进度消息"""
        if self.callback:
            try:
                await self.callback({"type": "progress", "message": message})
            except Exception as e:
                logger.error(f"Failed to send progress: {e}")


async def send_progress(message: str, websocket=None):
    """
    快捷函数：发送进度消息

    用法:
        await send_progress("正在搜索数据...", websocket)
    """
    if websocket:
        try:
            await websocket.send_json({"type": "progress", "message": message})
        except Exception as e:
            logger.error(f"Failed to send progress: {e}")

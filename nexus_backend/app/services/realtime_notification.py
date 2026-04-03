"""实时通知服务 - WebSocket推送
P0-3: 浏览器通知、钉钉/企微集成
"""

from fastapi import WebSocket

# 活跃连接管理
active_connections: dict[str, WebSocket] = {}


async def connect_websocket(websocket: WebSocket, user_id: str):
    """建立WebSocket连接"""
    await websocket.accept()
    active_connections[user_id] = websocket


async def disconnect_websocket(user_id: str):
    """断开连接"""
    if user_id in active_connections:
        del active_connections[user_id]


async def send_notification(user_id: str, message: dict):
    """发送实时通知"""
    if user_id in active_connections:
        ws = active_connections[user_id]
        await ws.send_json(message)

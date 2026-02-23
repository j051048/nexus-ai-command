"""
B2: Wecom (企业微信) Notification Adapter

企业微信群机器人 Webhook 通知适配器。

特性：
- 通过企业微信群机器人 Webhook 发送 markdown 消息
- 支持文本、markdown、图片、图文等多种消息类型
- 从 config 读取 WECOM_WEBHOOK_URL
- 发送失败记录日志，不抛出异常
- 支持 @all 和 @指定用户

官方文档：https://developer.work.weixin.qq.com/document/path/91770
"""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.services.notification_service import BaseNotificationAdapter, Notification

logger = logging.getLogger(__name__)


class WecomNotificationAdapter(BaseNotificationAdapter):
    """
    企业微信群机器人通知适配器

    通过企业微信群机器人 Webhook 发送通知。
    从 settings 读取配置：
    - WECOM_WEBHOOK_URL: 企业微信群机器人 Webhook 地址

    消息格式：
    - 默认使用 markdown 格式
    - 支持在 metadata 中指定消息类型：text, markdown, image, news
    - 支持 @all 或 @指定用户（通过 mentioned_list）

    示例 metadata：
    {
        "msgtype": "markdown",  # 消息类型（可选，默认 markdown）
        "mentioned_list": ["@all"],  # @提醒用户列表（可选）
        "mentioned_mobile_list": ["13800001111"]  # @手机号列表（可选）
    }
    """

    def __init__(self):
        """初始化企业微信适配器"""
        self.webhook_url: str | None = getattr(settings, "WECOM_WEBHOOK_URL", None)

        if not self.webhook_url:
            logger.warning(
                "Wecom notification adapter initialized without WECOM_WEBHOOK_URL. "
                "Wecom notifications will be disabled until configured."
            )
        else:
            logger.info(f"Wecom notification adapter initialized: url={self.webhook_url[:50]}...")

    async def send(self, notification: Notification) -> bool:
        """
        发送企业微信通知

        Args:
            notification: 通知对象
                - title: 通知标题
                - content: 通知内容（支持 markdown）
                - metadata: 扩展信息
                    - msgtype: 消息类型（text/markdown/image/news，默认 markdown）
                    - mentioned_list: @用户列表（userid 或 "@all"）
                    - mentioned_mobile_list: @手机号列表

        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        # 检查配置
        if not self.webhook_url:
            logger.warning(
                f"Cannot send wecom notification: WECOM_WEBHOOK_URL not configured, "
                f"notification_id={notification.notification_id}"
            )
            return False

        try:
            # 构建消息体
            payload = self._build_payload(notification)

            # 发送 Webhook 请求
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()

                # 检查企业微信返回结果
                result = response.json()
                if result.get("errcode") != 0:
                    logger.error(
                        f"Wecom API returned error: {result.get('errmsg')}, "
                        f"notification_id={notification.notification_id}"
                    )
                    return False

            logger.info(
                f"Wecom notification sent successfully: "
                f"title={notification.title[:50]}, "
                f"notification_id={notification.notification_id}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error sending wecom notification: {e.response.status_code} {e.response.text}, "
                f"notification_id={notification.notification_id}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(
                f"Request error sending wecom notification: {e}, " f"notification_id={notification.notification_id}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending wecom notification: {e}, " f"notification_id={notification.notification_id}"
            )
            return False

    def _build_payload(self, notification: Notification) -> dict[str, Any]:
        """
        构建企业微信消息载荷

        Args:
            notification: 通知对象

        Returns:
            Dict[str, Any]: Webhook 请求载荷
        """
        msgtype = notification.metadata.get("msgtype", "markdown")

        # 根据消息类型构建载荷
        if msgtype == "text":
            return self._build_text_payload(notification)
        elif msgtype == "markdown":
            return self._build_markdown_payload(notification)
        elif msgtype == "image":
            return self._build_image_payload(notification)
        elif msgtype == "news":
            return self._build_news_payload(notification)
        else:
            # 默认使用 markdown
            return self._build_markdown_payload(notification)

    def _build_text_payload(self, notification: Notification) -> dict[str, Any]:
        """
        构建文本消息载荷

        Args:
            notification: 通知对象

        Returns:
            Dict[str, Any]: 文本消息载荷
        """
        content = f"{notification.title}\n\n{notification.content}"

        payload = {"msgtype": "text", "text": {"content": content}}

        # 添加 @提醒
        mentioned_list = notification.metadata.get("mentioned_list", [])
        mentioned_mobile_list = notification.metadata.get("mentioned_mobile_list", [])
        if mentioned_list:
            payload["text"]["mentioned_list"] = mentioned_list
        if mentioned_mobile_list:
            payload["text"]["mentioned_mobile_list"] = mentioned_mobile_list

        return payload

    def _build_markdown_payload(self, notification: Notification) -> dict[str, Any]:
        """
        构建 markdown 消息载荷

        Args:
            notification: 通知对象

        Returns:
            Dict[str, Any]: Markdown 消息载荷
        """
        # 合并标题和内容为 markdown 格式
        markdown_content = f"## {notification.title}\n\n{notification.content}"

        return {"msgtype": "markdown", "markdown": {"content": markdown_content}}

    def _build_image_payload(self, notification: Notification) -> dict[str, Any]:
        """
        构建图片消息载荷

        Args:
            notification: 通知对象
                - metadata 中需要提供 image_base64 或 image_md5

        Returns:
            Dict[str, Any]: 图片消息载荷
        """
        image_data = {}

        if "image_base64" in notification.metadata:
            image_data["base64"] = notification.metadata["image_base64"]
            # 计算 md5（简化处理，生产环境需实际计算）
            import hashlib

            md5 = hashlib.md5(notification.metadata["image_base64"].encode()).hexdigest()
            image_data["md5"] = md5
        elif "image_md5" in notification.metadata:
            image_data["md5"] = notification.metadata["image_md5"]

        return {"msgtype": "image", "image": image_data}

    def _build_news_payload(self, notification: Notification) -> dict[str, Any]:
        """
        构建图文消息载荷

        Args:
            notification: 通知对象
                - metadata 中需要提供 articles 列表

        Returns:
            Dict[str, Any]: 图文消息载荷
        """
        articles = notification.metadata.get("articles", [])

        # 如果没有提供 articles，使用标题和内容构建一个默认 article
        if not articles:
            articles = [
                {
                    "title": notification.title,
                    "description": notification.content[:100],  # 限制描述长度
                    "url": notification.metadata.get("url", ""),
                    "picurl": notification.metadata.get("picurl", ""),
                }
            ]

        return {"msgtype": "news", "news": {"articles": articles}}

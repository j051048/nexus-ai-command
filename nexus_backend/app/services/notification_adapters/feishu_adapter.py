"""
B2: Feishu (飞书) Notification Adapter

飞书群机器人 Webhook 通知适配器。

特性：
- 通过飞书群机器人 Webhook 发送 interactive 卡片消息
- 支持文本、富文本、卡片等多种消息类型
- 从 config 读取 FEISHU_WEBHOOK_URL
- 发送失败记录日志，不抛出异常
- 支持 @all 和 @指定用户

官方文档：https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN
"""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.services.notification_service import BaseNotificationAdapter, Notification

logger = logging.getLogger(__name__)


class FeishuNotificationAdapter(BaseNotificationAdapter):
    """
    飞书群机器人通知适配器

    通过飞书群机器人 Webhook 发送通知。
    从 settings 读取配置：
    - FEISHU_WEBHOOK_URL: 飞书群机器人 Webhook 地址

    消息格式：
    - 默认使用 interactive 卡片消息
    - 支持在 metadata 中指定消息类型：text, post, interactive
    - 支持 @all 或 @指定用户（通过 at_user_ids）

    示例 metadata：
    {
        "msg_type": "interactive",  # 消息类型（可选，默认 interactive）
        "at_user_ids": ["ou_xxx"],  # @用户ID列表（可选）
        "at_all": false  # 是否@所有人（可选）
    }
    """

    def __init__(self):
        """初始化飞书适配器"""
        self.webhook_url: str | None = getattr(settings, "FEISHU_WEBHOOK_URL", None)

        if not self.webhook_url:
            logger.warning(
                "Feishu notification adapter initialized without FEISHU_WEBHOOK_URL. "
                "Feishu notifications will be disabled until configured."
            )
        else:
            logger.info(
                f"Feishu notification adapter initialized: url={self.webhook_url[:50]}..."
            )

    async def send(self, notification: Notification) -> bool:
        """
        发送飞书通知

        Args:
            notification: 通知对象
                - title: 通知标题
                - content: 通知内容（支持 markdown）
                - metadata: 扩展信息
                    - msg_type: 消息类型（text/post/interactive，默认 interactive）
                    - at_user_ids: @用户ID列表
                    - at_all: 是否@所有人

        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        # 检查配置
        if not self.webhook_url:
            logger.warning(
                f"Cannot send feishu notification: FEISHU_WEBHOOK_URL not configured, "
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

                # 检查飞书返回结果
                result = response.json()
                if result.get("code") != 0:
                    logger.error(
                        f"Feishu API returned error: {result.get('msg')}, "
                        f"notification_id={notification.notification_id}"
                    )
                    return False

            logger.info(
                f"Feishu notification sent successfully: "
                f"title={notification.title[:50]}, "
                f"notification_id={notification.notification_id}"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error sending feishu notification: {e.response.status_code} {e.response.text}, "
                f"notification_id={notification.notification_id}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(
                f"Request error sending feishu notification: {e}, notification_id={notification.notification_id}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending feishu notification: {e}, notification_id={notification.notification_id}"
            )
            return False

    def _build_payload(self, notification: Notification) -> dict[str, Any]:
        """
        构建飞书消息载荷

        Args:
            notification: 通知对象

        Returns:
            Dict[str, Any]: Webhook 请求载荷
        """
        msg_type = notification.metadata.get("msg_type", "interactive")

        # 根据消息类型构建载荷
        if msg_type == "text":
            return self._build_text_payload(notification)
        elif msg_type == "post":
            return self._build_post_payload(notification)
        elif msg_type == "interactive":
            return self._build_interactive_payload(notification)
        else:
            # 默认使用 interactive
            return self._build_interactive_payload(notification)

    def _build_text_payload(self, notification: Notification) -> dict[str, Any]:
        """
        构建文本消息载荷

        Args:
            notification: 通知对象

        Returns:
            Dict[str, Any]: 文本消息载荷
        """
        content = f"{notification.title}\n\n{notification.content}"

        # 添加 @信息
        at_content = self._build_at_text(notification)
        if at_content:
            content = f"{at_content}\n{content}"

        return {"msg_type": "text", "content": {"text": content}}

    def _build_post_payload(self, notification: Notification) -> dict[str, Any]:
        """
        构建富文本消息载荷

        Args:
            notification: 通知对象

        Returns:
            Dict[str, Any]: 富文本消息载荷
        """
        # 构建富文本内容
        post_content = [
            [{"tag": "text", "text": notification.title, "style": ["bold"]}],
            [{"tag": "text", "text": "\n"}],
        ]

        # 添加内容（支持简单的 markdown 解析）
        content_lines = notification.content.split("\n")
        for line in content_lines:
            if line.strip():
                post_content.append([{"tag": "text", "text": line}])

        # 添加 @信息
        at_list = self._build_at_list(notification)
        if at_list:
            post_content.insert(0, at_list)

        return {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {"title": notification.title, "content": post_content}
                }
            },
        }

    def _build_interactive_payload(self, notification: Notification) -> dict[str, Any]:
        """
        构建交互式卡片消息载荷

        Args:
            notification: 通知对象

        Returns:
            Dict[str, Any]: 交互式卡片消息载荷
        """
        # 构建卡片头部
        header = {
            "title": {"tag": "plain_text", "content": notification.title},
            "template": self._get_card_template(notification.priority),
        }

        # 构建卡片内容元素
        elements = []

        # 添加 @信息
        at_text = self._build_at_text(notification)
        if at_text:
            elements.append(
                {"tag": "div", "text": {"tag": "plain_text", "content": at_text}}
            )

        # 添加主要内容（支持 markdown）
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": notification.content}}
        )

        # 添加分割线
        elements.append({"tag": "hr"})

        # 添加元数据信息
        meta_info = self._build_meta_info(notification)
        if meta_info:
            elements.append(
                {"tag": "div", "text": {"tag": "lark_md", "content": meta_info}}
            )

        # 添加自定义按钮（如果提供）
        actions = notification.metadata.get("actions", [])
        if actions:
            elements.append({"tag": "action", "actions": actions})

        return {
            "msg_type": "interactive",
            "card": {"header": header, "elements": elements},
        }

    def _get_card_template(self, priority) -> str:
        """
        根据优先级获取卡片模板颜色

        Args:
            priority: 通知优先级

        Returns:
            str: 模板颜色（blue/wathet/turquoise/green/yellow/orange/red/carmine/violet/purple/indigo/grey）
        """
        from app.services.notification_service import NotificationPriority

        priority_template_map = {
            NotificationPriority.LOW: "grey",
            NotificationPriority.NORMAL: "blue",
            NotificationPriority.HIGH: "orange",
            NotificationPriority.URGENT: "red",
        }

        return priority_template_map.get(priority, "blue")

    def _build_at_text(self, notification: Notification) -> str:
        """
        构建 @文本

        Args:
            notification: 通知对象

        Returns:
            str: @文本（如 "@all" 或 "@用户列表"）
        """
        at_all = notification.metadata.get("at_all", False)
        if at_all:
            return "<at id=all></at>"

        at_user_ids = notification.metadata.get("at_user_ids", [])
        if at_user_ids:
            at_tags = [f"<at id={user_id}></at>" for user_id in at_user_ids]
            return " ".join(at_tags)

        return ""

    def _build_at_list(self, notification: Notification) -> list[dict[str, Any]]:
        """
        构建 @列表（用于富文本消息）

        Args:
            notification: 通知对象

        Returns:
            List[Dict[str, Any]]: @标签列表
        """
        at_list = []

        at_all = notification.metadata.get("at_all", False)
        if at_all:
            at_list.append({"tag": "at", "user_id": "all"})
            return at_list

        at_user_ids = notification.metadata.get("at_user_ids", [])
        for user_id in at_user_ids:
            at_list.append({"tag": "at", "user_id": user_id})

        return at_list

    def _build_meta_info(self, notification: Notification) -> str:
        """
        构建元数据信息（卡片底部显示）

        Args:
            notification: 通知对象

        Returns:
            str: 元数据信息（markdown 格式）
        """
        from app.services.notification_service import NotificationPriority

        priority_map = {
            NotificationPriority.LOW: "🔵 低",
            NotificationPriority.NORMAL: "🟢 普通",
            NotificationPriority.HIGH: "🟠 高",
            NotificationPriority.URGENT: "🔴 紧急",
        }

        priority_text = priority_map.get(notification.priority, "🟢 普通")
        timestamp = notification.created_at.strftime("%Y-%m-%d %H:%M:%S")

        return f"**优先级**: {priority_text}  |  **时间**: {timestamp}"

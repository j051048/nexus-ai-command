"""
B2: Notification Channel Adapters

通知渠道适配器模块，提供多种外部通知渠道的实现：
- EmailNotificationAdapter: 邮件通知（SMTP）
- WecomNotificationAdapter: 企业微信群机器人 Webhook
- DingtalkNotificationAdapter: 钉钉群机器人 Webhook（支持加签）
- FeishuNotificationAdapter: 飞书群机器人 Webhook
"""

from .dingtalk_adapter import DingtalkNotificationAdapter
from .email_adapter import EmailNotificationAdapter
from .feishu_adapter import FeishuNotificationAdapter
from .wecom_adapter import WecomNotificationAdapter

__all__ = [
    "EmailNotificationAdapter",
    "WecomNotificationAdapter",
    "DingtalkNotificationAdapter",
    "FeishuNotificationAdapter",
]

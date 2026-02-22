"""
IM 平台深度集成模块

提供企微/钉钉/飞书的完整 API 客户端，支持：
- Token 管理（自动缓存和刷新）
- 通讯录同步（部门 + 用户）
- 考勤数据同步
- OAuth SSO 登录
- 互动消息卡片（含审批按钮）
"""

from .base_client import IMPlatformClient
from .dingtalk_client import DingtalkClient
from .feishu_client import FeishuClient
from .wecom_client import WecomClient

__all__ = [
    "IMPlatformClient",
    "WecomClient",
    "DingtalkClient",
    "FeishuClient",
]

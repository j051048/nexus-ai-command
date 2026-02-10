"""
B1: Unified Notification Service

统一通知服务，作为所有通知渠道的中枢。
支持站内、邮件、企业微信、钉钉、飞书等多渠道通知。

特性：
- 抽象适配器模式，支持多渠道扩展
- 优先级管理（low, normal, high, urgent）
- 多渠道同时发送
- 按角色群发
- 发送失败记录日志，不阻塞主流程
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from app.core.database import supabase

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    """通知渠道枚举"""
    IN_APP = "in_app"
    EMAIL = "email"
    WECOM = "wecom"
    DINGTALK = "dingtalk"
    FEISHU = "feishu"


class NotificationPriority(str, Enum):
    """通知优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """
    通知数据类
    
    Attributes:
        title: 通知标题
        content: 通知内容
        target_user_id: 目标用户ID
        channel: 通知渠道
        priority: 通知优先级
        metadata: 扩展元数据（可选）
        notification_id: 通知唯一ID（自动生成）
        created_at: 创建时间（自动生成）
    """
    title: str
    content: str
    target_user_id: str
    channel: NotificationChannel
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "notification_id": self.notification_id,
            "title": self.title,
            "content": self.content,
            "target_user_id": self.target_user_id,
            "channel": self.channel.value if isinstance(self.channel, Enum) else self.channel,
            "priority": self.priority.value if isinstance(self.priority, Enum) else self.priority,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at
        }


class BaseNotificationAdapter(ABC):
    """
    通知适配器抽象基类
    
    所有通知渠道适配器必须继承此类并实现 send 方法
    """
    
    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """
        发送通知
        
        Args:
            notification: 通知对象
            
        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        pass


class InAppNotificationAdapter(BaseNotificationAdapter):
    """
    站内通知适配器
    
    往数据库 notifications 表写入通知记录
    """
    
    async def send(self, notification: Notification) -> bool:
        """
        发送站内通知
        
        Args:
            notification: 通知对象
            
        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        try:
            if not supabase:
                logger.warning("Supabase client not configured, skipping in-app notification")
                return False
            
            # 映射优先级到通知类型（兼容现有表结构）
            notification_type = self._map_priority_to_type(notification.priority)
            
            # 准备插入数据
            data = {
                "user_id": notification.target_user_id,
                "title": notification.title,
                "content": notification.content,
                "type": notification_type,
                "metadata": notification.metadata
            }
            
            # 插入数据库
            await supabase.table("notifications").insert(data).execute()
            
            logger.info(
                f"In-app notification sent successfully: "
                f"user_id={notification.target_user_id}, "
                f"title={notification.title[:50]}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to send in-app notification: {e}, "
                f"user_id={notification.target_user_id}, "
                f"title={notification.title[:50]}"
            )
            return False
    
    @staticmethod
    def _map_priority_to_type(priority: NotificationPriority) -> str:
        """
        映射优先级到通知类型（兼容现有数据库结构）
        
        Args:
            priority: 通知优先级
            
        Returns:
            str: 通知类型（success/warning/info/error）
        """
        mapping = {
            NotificationPriority.LOW: "info",
            NotificationPriority.NORMAL: "success",
            NotificationPriority.HIGH: "warning",
            NotificationPriority.URGENT: "error"
        }
        return mapping.get(priority, "success")


class NotificationService:
    """
    统一通知服务
    
    负责：
    - 注册和管理通知渠道适配器
    - 单渠道发送
    - 多渠道同时发送
    - 按角色群发
    """
    
    def __init__(self):
        """初始化通知服务"""
        self._adapters: Dict[NotificationChannel, BaseNotificationAdapter] = {}
        logger.info("NotificationService initialized")
    
    def register_adapter(
        self,
        channel: NotificationChannel,
        adapter: BaseNotificationAdapter
    ) -> None:
        """
        注册通知渠道适配器
        
        Args:
            channel: 通知渠道
            adapter: 适配器实例
        """
        self._adapters[channel] = adapter
        logger.info(f"Registered notification adapter: {channel.value}")
    
    async def send(self, notification: Notification) -> bool:
        """
        发送单个通知
        
        根据通知对象的 channel 属性选择对应适配器发送
        发送失败记录日志，不抛出异常
        
        Args:
            notification: 通知对象
            
        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        channel = notification.channel
        
        if channel not in self._adapters:
            logger.warning(
                f"No adapter registered for channel: {channel.value}, "
                f"notification_id={notification.notification_id}"
            )
            return False
        
        adapter = self._adapters[channel]
        
        try:
            result = await adapter.send(notification)
            return result
        except Exception as e:
            logger.error(
                f"Unexpected error sending notification via {channel.value}: {e}, "
                f"notification_id={notification.notification_id}"
            )
            return False
    
    async def send_multi(
        self,
        notification: Notification,
        channels: List[NotificationChannel]
    ) -> Dict[NotificationChannel, bool]:
        """
        多渠道同时发送通知
        
        向指定的多个渠道同时发送同一条通知
        每个渠道独立发送，失败不影响其他渠道
        
        Args:
            notification: 通知对象（channel 字段会被覆盖）
            channels: 要发送的渠道列表
            
        Returns:
            Dict[NotificationChannel, bool]: 各渠道发送结果映射
        """
        results = {}
        
        for channel in channels:
            # 克隆通知对象并设置渠道
            channel_notification = Notification(
                title=notification.title,
                content=notification.content,
                target_user_id=notification.target_user_id,
                channel=channel,
                priority=notification.priority,
                metadata=notification.metadata,
                notification_id=notification.notification_id,
                created_at=notification.created_at
            )
            
            success = await self.send(channel_notification)
            results[channel] = success
        
        # 记录汇总结果
        success_count = sum(1 for v in results.values() if v)
        logger.info(
            f"Multi-channel send completed: "
            f"{success_count}/{len(channels)} succeeded, "
            f"notification_id={notification.notification_id}"
        )
        
        return results
    
    async def send_to_role(
        self,
        title: str,
        content: str,
        role: str,
        channels: List[NotificationChannel],
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Dict[NotificationChannel, bool]]:
        """
        按角色群发通知
        
        查询指定角色的所有用户，向每个用户的指定渠道发送通知
        
        Args:
            title: 通知标题
            content: 通知内容
            role: 目标角色（boss/admin/manager/employee等）
            channels: 要发送的渠道列表
            priority: 通知优先级
            metadata: 扩展元数据（可选）
            
        Returns:
            Dict[str, Dict[NotificationChannel, bool]]: 用户ID -> 渠道发送结果映射
        """
        if not supabase:
            logger.warning("Supabase client not configured, cannot send role-based notifications")
            return {}
        
        try:
            # 查询指定角色的所有用户
            result = await supabase.table("users").select("id").eq("role", role).execute()
            
            if not result.data:
                logger.warning(f"No users found with role: {role}")
                return {}
            
            user_ids = [user["id"] for user in result.data]
            logger.info(f"Found {len(user_ids)} users with role: {role}")
            
            # 向每个用户发送通知
            all_results = {}
            
            for user_id in user_ids:
                notification = Notification(
                    title=title,
                    content=content,
                    target_user_id=user_id,
                    channel=NotificationChannel.IN_APP,  # 占位，send_multi 会覆盖
                    priority=priority,
                    metadata=metadata or {}
                )
                
                user_results = await self.send_multi(notification, channels)
                all_results[user_id] = user_results
            
            # 统计发送结果
            total_sends = len(user_ids) * len(channels)
            total_success = sum(
                sum(1 for v in user_results.values() if v)
                for user_results in all_results.values()
            )
            
            logger.info(
                f"Role-based send completed: "
                f"{total_success}/{total_sends} succeeded, "
                f"role={role}, users={len(user_ids)}, channels={len(channels)}"
            )
            
            return all_results
            
        except Exception as e:
            logger.error(f"Failed to send role-based notifications: {e}, role={role}")
            return {}


# ============== Global Instance ==============

# 创建全局通知服务实例
notification_service = NotificationService()

# 默认注册站内通知适配器
notification_service.register_adapter(
    NotificationChannel.IN_APP,
    InAppNotificationAdapter()
)

logger.info("Global notification_service initialized with in_app adapter")


# ============== Convenience Functions ==============

async def send_notification(
    title: str,
    content: str,
    target_user_id: str,
    channel: NotificationChannel = NotificationChannel.IN_APP,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    便捷函数：发送单个通知
    
    Args:
        title: 通知标题
        content: 通知内容
        target_user_id: 目标用户ID
        channel: 通知渠道（默认站内）
        priority: 通知优先级（默认normal）
        metadata: 扩展元数据（可选）
        
    Returns:
        bool: 发送成功返回 True，失败返回 False
    """
    notification = Notification(
        title=title,
        content=content,
        target_user_id=target_user_id,
        channel=channel,
        priority=priority,
        metadata=metadata or {}
    )
    return await notification_service.send(notification)


async def send_multi_channel(
    title: str,
    content: str,
    target_user_id: str,
    channels: List[NotificationChannel],
    priority: NotificationPriority = NotificationPriority.NORMAL,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[NotificationChannel, bool]:
    """
    便捷函数：多渠道发送通知
    
    Args:
        title: 通知标题
        content: 通知内容
        target_user_id: 目标用户ID
        channels: 通知渠道列表
        priority: 通知优先级（默认normal）
        metadata: 扩展元数据（可选）
        
    Returns:
        Dict[NotificationChannel, bool]: 各渠道发送结果映射
    """
    notification = Notification(
        title=title,
        content=content,
        target_user_id=target_user_id,
        channel=NotificationChannel.IN_APP,  # 占位，send_multi 会覆盖
        priority=priority,
        metadata=metadata or {}
    )
    return await notification_service.send_multi(notification, channels)

"""
B2: Dingtalk (钉钉) Notification Adapter

钉钉群机器人 Webhook 通知适配器。

特性：
- 通过钉钉群机器人 Webhook 发送 markdown 消息
- 支持加签安全验证（HMAC-SHA256）
- 支持文本、link、markdown、ActionCard 等多种消息类型
- 从 config 读取 DINGTALK_WEBHOOK_URL 和 DINGTALK_SECRET
- 发送失败记录日志，不抛出异常
- 支持 @all 和 @指定用户

官方文档：https://open.dingtalk.com/document/robots/custom-robot-access
"""
import logging
import time
import hmac
import hashlib
import base64
from urllib.parse import quote_plus
from typing import Optional, Dict, Any

import httpx

from app.services.notification_service import BaseNotificationAdapter, Notification
from app.core.config import settings

logger = logging.getLogger(__name__)


class DingtalkNotificationAdapter(BaseNotificationAdapter):
    """
    钉钉群机器人通知适配器
    
    通过钉钉群机器人 Webhook 发送通知，支持加签验证。
    从 settings 读取配置：
    - DINGTALK_WEBHOOK_URL: 钉钉群机器人 Webhook 地址
    - DINGTALK_SECRET: 加签密钥（可选，但推荐配置）
    
    消息格式：
    - 默认使用 markdown 格式
    - 支持在 metadata 中指定消息类型：text, link, markdown, actionCard
    - 支持 @all 或 @指定用户（通过 atMobiles 或 atUserIds）
    
    示例 metadata：
    {
        "msgtype": "markdown",  # 消息类型（可选，默认 markdown）
        "atMobiles": ["13800001111"],  # @手机号列表（可选）
        "atUserIds": ["user123"],  # @用户ID列表（可选）
        "isAtAll": false  # 是否@所有人（可选）
    }
    """
    
    def __init__(self):
        """初始化钉钉适配器"""
        self.webhook_url: Optional[str] = getattr(settings, "DINGTALK_WEBHOOK_URL", None)
        self.secret: Optional[str] = getattr(settings, "DINGTALK_SECRET", None)
        
        if not self.webhook_url:
            logger.warning(
                "Dingtalk notification adapter initialized without DINGTALK_WEBHOOK_URL. "
                "Dingtalk notifications will be disabled until configured."
            )
        else:
            if not self.secret:
                logger.warning(
                    "Dingtalk notification adapter initialized without DINGTALK_SECRET. "
                    "Signature verification is disabled (not recommended for production)."
                )
            logger.info(
                f"Dingtalk notification adapter initialized: "
                f"url={self.webhook_url[:50]}..., "
                f"secret={'configured' if self.secret else 'not configured'}"
            )
    
    async def send(self, notification: Notification) -> bool:
        """
        发送钉钉通知
        
        Args:
            notification: 通知对象
                - title: 通知标题
                - content: 通知内容（支持 markdown）
                - metadata: 扩展信息
                    - msgtype: 消息类型（text/link/markdown/actionCard，默认 markdown）
                    - atMobiles: @手机号列表
                    - atUserIds: @用户ID列表
                    - isAtAll: 是否@所有人
            
        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        # 检查配置
        if not self.webhook_url:
            logger.warning(
                f"Cannot send dingtalk notification: DINGTALK_WEBHOOK_URL not configured, "
                f"notification_id={notification.notification_id}"
            )
            return False
        
        try:
            # 构建完整 URL（包含签名）
            url = self._build_signed_url()
            
            # 构建消息体
            payload = self._build_payload(notification)
            
            # 发送 Webhook 请求
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                # 检查钉钉返回结果
                result = response.json()
                if result.get("errcode") != 0:
                    logger.error(
                        f"Dingtalk API returned error: {result.get('errmsg')}, "
                        f"notification_id={notification.notification_id}"
                    )
                    return False
            
            logger.info(
                f"Dingtalk notification sent successfully: "
                f"title={notification.title[:50]}, "
                f"notification_id={notification.notification_id}"
            )
            return True
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error sending dingtalk notification: {e.response.status_code} {e.response.text}, "
                f"notification_id={notification.notification_id}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(
                f"Request error sending dingtalk notification: {e}, "
                f"notification_id={notification.notification_id}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending dingtalk notification: {e}, "
                f"notification_id={notification.notification_id}"
            )
            return False
    
    def _build_signed_url(self) -> str:
        """
        构建带签名的 Webhook URL
        
        钉钉加签算法：
        1. 把 timestamp+"\n"+secret 当做签名字符串
        2. 使用 HmacSHA256 算法计算签名
        3. 对签名进行 Base64 编码
        4. 对编码后的签名进行 URL encode
        
        Returns:
            str: 带签名参数的完整 URL
        """
        url = self.webhook_url
        
        # 如果没有配置 secret，直接返回原始 URL
        if not self.secret:
            return url
        
        # 计算签名
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        sign = quote_plus(base64.b64encode(hmac_code))
        
        # 拼接 URL
        separator = "&" if "?" in url else "?"
        signed_url = f"{url}{separator}timestamp={timestamp}&sign={sign}"
        
        return signed_url
    
    def _build_payload(self, notification: Notification) -> Dict[str, Any]:
        """
        构建钉钉消息载荷
        
        Args:
            notification: 通知对象
            
        Returns:
            Dict[str, Any]: Webhook 请求载荷
        """
        msgtype = notification.metadata.get("msgtype", "markdown")
        
        # 根据消息类型构建载荷
        if msgtype == "text":
            return self._build_text_payload(notification)
        elif msgtype == "link":
            return self._build_link_payload(notification)
        elif msgtype == "markdown":
            return self._build_markdown_payload(notification)
        elif msgtype == "actionCard":
            return self._build_action_card_payload(notification)
        else:
            # 默认使用 markdown
            return self._build_markdown_payload(notification)
    
    def _build_text_payload(self, notification: Notification) -> Dict[str, Any]:
        """
        构建文本消息载荷
        
        Args:
            notification: 通知对象
            
        Returns:
            Dict[str, Any]: 文本消息载荷
        """
        content = f"{notification.title}\n\n{notification.content}"
        
        payload = {
            "msgtype": "text",
            "text": {
                "content": content
            },
            "at": self._build_at_info(notification)
        }
        
        return payload
    
    def _build_link_payload(self, notification: Notification) -> Dict[str, Any]:
        """
        构建链接消息载荷
        
        Args:
            notification: 通知对象
                - metadata 需要提供 messageUrl（必需）、picUrl（可选）
            
        Returns:
            Dict[str, Any]: 链接消息载荷
        """
        return {
            "msgtype": "link",
            "link": {
                "title": notification.title,
                "text": notification.content,
                "messageUrl": notification.metadata.get("messageUrl", ""),
                "picUrl": notification.metadata.get("picUrl", "")
            }
        }
    
    def _build_markdown_payload(self, notification: Notification) -> Dict[str, Any]:
        """
        构建 markdown 消息载荷
        
        Args:
            notification: 通知对象
            
        Returns:
            Dict[str, Any]: Markdown 消息载荷
        """
        # 合并标题和内容为 markdown 格式
        markdown_content = f"## {notification.title}\n\n{notification.content}"
        
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": notification.title,
                "text": markdown_content
            },
            "at": self._build_at_info(notification)
        }
    
    def _build_action_card_payload(self, notification: Notification) -> Dict[str, Any]:
        """
        构建 ActionCard 消息载荷
        
        Args:
            notification: 通知对象
                - metadata 需要提供 singleTitle 和 singleURL（单按钮模式）
                  或 btns 列表（多按钮模式）
            
        Returns:
            Dict[str, Any]: ActionCard 消息载荷
        """
        action_card = {
            "title": notification.title,
            "text": notification.content,
        }
        
        # 单按钮模式
        if "singleTitle" in notification.metadata and "singleURL" in notification.metadata:
            action_card["singleTitle"] = notification.metadata["singleTitle"]
            action_card["singleURL"] = notification.metadata["singleURL"]
        # 多按钮模式
        elif "btns" in notification.metadata:
            action_card["btns"] = notification.metadata["btns"]
            action_card["btnOrientation"] = notification.metadata.get("btnOrientation", "0")
        
        return {
            "msgtype": "actionCard",
            "actionCard": action_card
        }
    
    def _build_at_info(self, notification: Notification) -> Dict[str, Any]:
        """
        构建 @信息
        
        Args:
            notification: 通知对象
            
        Returns:
            Dict[str, Any]: @信息字典
        """
        at_info = {}
        
        at_mobiles = notification.metadata.get("atMobiles", [])
        at_user_ids = notification.metadata.get("atUserIds", [])
        is_at_all = notification.metadata.get("isAtAll", False)
        
        if at_mobiles:
            at_info["atMobiles"] = at_mobiles
        if at_user_ids:
            at_info["atUserIds"] = at_user_ids
        
        at_info["isAtAll"] = is_at_all
        
        return at_info

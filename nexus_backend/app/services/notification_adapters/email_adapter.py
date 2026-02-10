"""
B2: Email Notification Adapter

邮件通知适配器，使用 aiosmtplib 异步发送邮件。

特性：
- 异步 SMTP 发送
- 支持 HTML 和纯文本邮件
- 从 config 读取 SMTP 配置
- 发送失败记录日志，不抛出异常
- 支持 TLS/STARTTLS
"""
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import aiosmtplib

from app.services.notification_service import BaseNotificationAdapter, Notification
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailNotificationAdapter(BaseNotificationAdapter):
    """
    邮件通知适配器
    
    使用 aiosmtplib 异步发送邮件。
    从 settings 读取 SMTP 配置：
    - SMTP_HOST: SMTP 服务器地址
    - SMTP_PORT: SMTP 端口（默认 587）
    - SMTP_USER: SMTP 用户名
    - SMTP_PASSWORD: SMTP 密码
    - SMTP_FROM: 发件人地址
    
    注意：
    - 如果 SMTP 配置不完整，发送将失败并记录警告
    - 默认使用 STARTTLS（端口 587）
    - 如果使用端口 465，会自动切换到 SSL
    - 邮件内容支持 HTML 和纯文本双格式
    """
    
    def __init__(self):
        """初始化邮件适配器"""
        self.smtp_host: Optional[str] = getattr(settings, "SMTP_HOST", None)
        self.smtp_port: int = getattr(settings, "SMTP_PORT", 587)
        self.smtp_user: Optional[str] = getattr(settings, "SMTP_USER", None)
        self.smtp_password: Optional[str] = getattr(settings, "SMTP_PASSWORD", None)
        self.smtp_from: Optional[str] = getattr(settings, "SMTP_FROM", None)
        
        # 检查配置完整性
        self._config_complete = all([
            self.smtp_host,
            self.smtp_user,
            self.smtp_password,
            self.smtp_from
        ])
        
        if not self._config_complete:
            logger.warning(
                "Email notification adapter initialized with incomplete SMTP configuration. "
                "Email sending will be disabled until SMTP_HOST, SMTP_USER, SMTP_PASSWORD, "
                "and SMTP_FROM are configured."
            )
        else:
            logger.info(
                f"Email notification adapter initialized: "
                f"host={self.smtp_host}, port={self.smtp_port}, from={self.smtp_from}"
            )
    
    async def send(self, notification: Notification) -> bool:
        """
        发送邮件通知
        
        Args:
            notification: 通知对象
                - title: 邮件主题
                - content: 邮件正文（支持 HTML）
                - target_user_id: 收件人邮箱地址（需要在 metadata 中提供）
                - metadata: 扩展信息
                    - email: 收件人邮箱（必需）
                    - cc: 抄送地址列表（可选）
                    - bcc: 密送地址列表（可选）
            
        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        # 检查 SMTP 配置
        if not self._config_complete:
            logger.warning(
                f"Cannot send email notification: SMTP not configured, "
                f"notification_id={notification.notification_id}"
            )
            return False
        
        # 提取收件人邮箱
        recipient_email = notification.metadata.get("email")
        if not recipient_email:
            logger.error(
                f"Cannot send email notification: no 'email' in metadata, "
                f"notification_id={notification.notification_id}"
            )
            return False
        
        try:
            # 构建邮件
            message = self._build_message(notification, recipient_email)
            
            # 发送邮件
            await self._send_smtp(message, recipient_email)
            
            logger.info(
                f"Email notification sent successfully: "
                f"to={recipient_email}, "
                f"subject={notification.title[:50]}, "
                f"notification_id={notification.notification_id}"
            )
            return True
            
        except aiosmtplib.SMTPException as e:
            logger.error(
                f"SMTP error sending email notification: {e}, "
                f"to={recipient_email}, "
                f"notification_id={notification.notification_id}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending email notification: {e}, "
                f"to={recipient_email}, "
                f"notification_id={notification.notification_id}"
            )
            return False
    
    def _build_message(
        self,
        notification: Notification,
        recipient_email: str
    ) -> MIMEMultipart:
        """
        构建 MIME 邮件消息
        
        Args:
            notification: 通知对象
            recipient_email: 收件人邮箱
            
        Returns:
            MIMEMultipart: 邮件消息对象
        """
        # 创建多部分邮件（支持纯文本和 HTML）
        message = MIMEMultipart("alternative")
        message["Subject"] = notification.title
        message["From"] = self.smtp_from
        message["To"] = recipient_email
        
        # 添加抄送和密送
        cc = notification.metadata.get("cc", [])
        bcc = notification.metadata.get("bcc", [])
        if cc:
            message["Cc"] = ", ".join(cc)
        if bcc:
            message["Bcc"] = ", ".join(bcc)
        
        # 纯文本版本（去除 HTML 标签）
        text_content = self._strip_html(notification.content)
        text_part = MIMEText(text_content, "plain", "utf-8")
        message.attach(text_part)
        
        # HTML 版本（如果内容包含 HTML 标签）
        if self._is_html(notification.content):
            html_part = MIMEText(notification.content, "html", "utf-8")
            message.attach(html_part)
        
        return message
    
    async def _send_smtp(
        self,
        message: MIMEMultipart,
        recipient_email: str
    ) -> None:
        """
        通过 SMTP 发送邮件
        
        Args:
            message: 邮件消息对象
            recipient_email: 收件人邮箱
            
        Raises:
            aiosmtplib.SMTPException: SMTP 发送失败
        """
        # 确定是否使用 SSL（端口 465）
        use_tls = (self.smtp_port == 465)
        
        # 准备收件人列表（包括抄送和密送）
        recipients = [recipient_email]
        if "Cc" in message:
            recipients.extend(message["Cc"].split(", "))
        if "Bcc" in message:
            recipients.extend(message["Bcc"].split(", "))
        
        # 发送邮件
        async with aiosmtplib.SMTP(
            hostname=self.smtp_host,
            port=self.smtp_port,
            use_tls=use_tls
        ) as smtp:
            # 如果不是 SSL，使用 STARTTLS
            if not use_tls:
                await smtp.starttls()
            
            # 登录
            await smtp.login(self.smtp_user, self.smtp_password)
            
            # 发送
            await smtp.send_message(message, recipients=recipients)
    
    @staticmethod
    def _is_html(content: str) -> bool:
        """
        检查内容是否包含 HTML 标签
        
        Args:
            content: 邮件内容
            
        Returns:
            bool: 是否为 HTML 内容
        """
        html_tags = ["<html", "<body", "<div", "<p>", "<br>", "<span", "<a ", "<img "]
        return any(tag in content.lower() for tag in html_tags)
    
    @staticmethod
    def _strip_html(content: str) -> str:
        """
        简单的 HTML 标签去除（用于纯文本版本）
        
        Args:
            content: 可能包含 HTML 的内容
            
        Returns:
            str: 纯文本内容
        """
        import re
        # 简单的标签去除（生产环境建议使用 BeautifulSoup）
        text = re.sub(r'<[^>]+>', '', content)
        # 解码 HTML 实体
        text = text.replace("&nbsp;", " ")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&amp;", "&")
        return text.strip()

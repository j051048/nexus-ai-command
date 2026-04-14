"""
WeChat Work (企业微信) Integration Service

提供企业微信消息回调处理能力:
- 消息签名验证
- XML 消息解析
- AI 消息处理
- 回复格式化

注意: 此为 API 准备层，实际接入需要在企微管理后台配置回调 URL。
"""

import hashlib
import logging
import os
import time
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# 企微配置（从环境变量读取）
WECOM_TOKEN = os.getenv("WECOM_TOKEN", "")
WECOM_ENCODING_AES_KEY = os.getenv("WECOM_ENCODING_AES_KEY", "")
WECOM_CORP_ID = os.getenv("WECOM_CORP_ID", "")
WECOM_AGENT_ID = os.getenv("WECOM_AGENT_ID", "")
WECOM_SECRET = os.getenv("WECOM_SECRET", "")


class WeComService:
    """企业微信消息处理服务"""

    def verify_signature(
        self, signature: str, timestamp: str, nonce: str, echostr: str = ""
    ) -> tuple[bool, str]:
        """验证企微回调签名

        Args:
            signature: 微信签名
            timestamp: 时间戳
            nonce: 随机数
            echostr: 回声字符串（验证 URL 时使用）

        Returns:
            (is_valid, echostr_or_error)
        """
        if not WECOM_TOKEN:
            return False, "WECOM_TOKEN 未配置"

        try:
            params = sorted([WECOM_TOKEN, timestamp, nonce])
            sign_str = "".join(params)
            computed_signature = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()

            if computed_signature == signature:
                return True, echostr
            return False, "签名验证失败"
        except Exception as e:
            logger.error(f"WeChat signature verification error: {e}")
            return False, str(e)

    def parse_xml_message(self, xml_body: str) -> dict:
        """解析企微消息 XML

        Args:
            xml_body: XML 格式的消息体

        Returns:
            解析后的消息字典
        """
        try:
            root = ET.fromstring(xml_body)
            msg = {}
            for child in root:
                msg[child.tag] = child.text
            return msg
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return {}

    def format_text_reply(
        self,
        to_user: str,
        from_user: str,
        content: str,
    ) -> str:
        """格式化文本回复 XML

        Args:
            to_user: 接收方
            from_user: 发送方（企业号）
            content: 回复内容

        Returns:
            XML 格式的回复
        """
        timestamp = int(time.time())
        return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{timestamp}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""

    async def handle_text_message(self, msg: dict) -> str:
        """处理文本消息，调用 AI 生成回复

        Args:
            msg: 解析后的消息字典

        Returns:
            AI 回复内容
        """
        user_content = msg.get("Content", "").strip()
        from_user = msg.get("FromUserName", "")

        if not user_content:
            return "收到空消息，请输入您的问题。"

        try:
            from app.services.chat_service import ChatService

            chat_service = ChatService()
            result = await chat_service.send_message(
                user_id=f"wecom_{from_user}",
                org_id="default",
                message=user_content,
                session_id=f"wecom_{from_user}",
            )

            response = result.get("response", "")
            if not response:
                return "AI 助手暂时无法回答，请稍后重试。"

            # 企微文本消息限制 2048 字符
            if len(response) > 2000:
                response = response[:1997] + "..."

            return response

        except Exception as e:
            logger.error(f"WeChat AI processing error: {e}")
            return "处理您的消息时出现错误，请稍后重试。"

    def handle_unsupported_message(self, msg_type: str) -> str:
        """处理不支持的消息类型

        Args:
            msg_type: 消息类型

        Returns:
            友好提示
        """
        type_names = {
            "image": "图片",
            "voice": "语音",
            "video": "视频",
            "location": "位置",
            "link": "链接",
            "file": "文件",
        }
        name = type_names.get(msg_type, msg_type)
        return f"暂不支持{name}消息，请发送文字消息与 AI 助手对话。"

    async def send_template_notification(
        self,
        user_id: str,
        title: str,
        content: str,
        url: str = "",
    ) -> bool:
        """通过企微消息模板发送通知（如审批通知）

        注意: 需要 WECOM_SECRET 和 access_token，
        此方法为框架实现，实际推送需要获取 access_token。

        Args:
            user_id: 企微用户 ID
            title: 通知标题
            content: 通知内容
            url: 跳转 URL

        Returns:
            是否发送成功
        """
        if not WECOM_CORP_ID or not WECOM_SECRET:
            logger.warning("WeChat Work notification skipped: WECOM_CORP_ID or WECOM_SECRET not configured")
            return False

        try:
            import httpx

            # Step 1: 获取 access_token
            token_url = (
                f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
                f"?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
            )
            async with httpx.AsyncClient() as client:
                token_resp = await client.get(token_url)
                token_data = token_resp.json()
                access_token = token_data.get("access_token")

                if not access_token:
                    logger.error(f"WeChat access_token fetch failed: {token_data}")
                    return False

                # Step 2: 发送消息
                send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
                payload = {
                    "touser": user_id,
                    "msgtype": "textcard",
                    "agentid": int(WECOM_AGENT_ID) if WECOM_AGENT_ID else 0,
                    "textcard": {
                        "title": title,
                        "description": content,
                        "url": url or "https://app.nexus-ai.com",
                    },
                }
                send_resp = await client.post(send_url, json=payload)
                result = send_resp.json()

                if result.get("errcode") == 0:
                    logger.info(f"WeChat notification sent to {user_id}")
                    return True
                else:
                    logger.error(f"WeChat notification failed: {result}")
                    return False

        except Exception as e:
            logger.error(f"WeChat notification error: {e}")
            return False


# 全局实例
wecom_service = WeComService()

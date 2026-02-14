"""
企业微信完整 API 客户端

基于企微服务端 API 实现完整功能：
- Token 获取与管理
- 通讯录同步（部门 + 用户列表）
- 考勤打卡数据拉取
- 应用消息推送（文本 + 互动模板卡片）
- OAuth2.0 网页授权（SSO 登录）

官方文档：https://developer.work.weixin.qq.com/document/
"""

import logging
from datetime import datetime
from typing import Dict, List, Any
from urllib.parse import quote

from app.services.im_platform.base_client import IMPlatformClient

logger = logging.getLogger(__name__)


class WecomClient(IMPlatformClient):
    """
    企业微信完整 API 客户端。

    企微 API 特点：
    - access_token 通过 GET /gettoken?corpid=xxx&corpsecret=xxx 获取
    - 大部分接口通过 query param 传递 access_token
    - 业务错误码: errcode == 0 表示成功（基类默认行为）
    """

    BASE_URL = "https://qyapi.weixin.qq.com/cgi-bin"

    def __init__(self, corp_id: str, corp_secret: str, agent_id: str = ""):
        """
        初始化企业微信客户端。

        Args:
            corp_id: 企业 ID (CorpID)
            corp_secret: 应用 Secret
            agent_id: 应用 AgentId（发送消息时需要）
        """
        super().__init__("wecom")
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = agent_id

    # ── Token ─────────────────────────────────────────────────────

    async def _fetch_access_token(self) -> Dict[str, Any]:
        """
        获取企微 access_token。
        GET https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=xxx&corpsecret=xxx

        Returns:
            {"access_token": "xxx", "expires_in": 7200}
        """
        client = await self._get_http_client()
        url = f"{self.BASE_URL}/gettoken"
        params = {
            "corpid": self.corp_id,
            "corpsecret": self.corp_secret,
        }

        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("errcode", 0) != 0:
            raise Exception(
                f"Wecom gettoken error: {data.get('errmsg', 'unknown')}"
            )

        return {
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 7200),
        }

    # ── Contact / Directory ───────────────────────────────────────

    async def get_departments(self) -> List[Dict]:
        """
        获取企业部门列表。
        GET /department/list

        Returns:
            [{"id": "1", "name": "总部", "parentid": "0", "order": 1}, ...]
        """
        url = f"{self.BASE_URL}/department/list"
        try:
            data = await self._api_request("GET", url)
            departments = data.get("department", [])
            # 标准化字段
            return [
                {
                    "id": str(dept.get("id", "")),
                    "name": dept.get("name", ""),
                    "parentid": str(dept.get("parentid", "0")),
                    "order": dept.get("order", 0),
                }
                for dept in departments
            ]
        except Exception as e:
            logger.error(f"[wecom] Failed to get departments: {e}")
            return []

    async def get_department_users(self, department_id: str) -> List[Dict]:
        """
        获取部门下的用户详细列表。
        GET /user/list?department_id=xxx

        Args:
            department_id: 部门 ID

        Returns:
            [{"userid": "xxx", "name": "张三", "mobile": "138...",
              "email": "...", "department": [1], "position": "..."}, ...]
        """
        url = f"{self.BASE_URL}/user/list"
        try:
            data = await self._api_request(
                "GET", url, params={"department_id": department_id}
            )
            user_list = data.get("userlist", [])
            return [
                {
                    "userid": user.get("userid", ""),
                    "name": user.get("name", ""),
                    "mobile": user.get("mobile", ""),
                    "email": user.get("email", ""),
                    "department": user.get("department", []),
                    "position": user.get("position", ""),
                    "gender": user.get("gender", 0),
                    "avatar": user.get("avatar", ""),
                    "status": user.get("status", 0),
                }
                for user in user_list
            ]
        except Exception as e:
            logger.error(
                f"[wecom] Failed to get users for department {department_id}: {e}"
            )
            return []

    # ── Attendance ────────────────────────────────────────────────

    async def get_attendance_records(
        self, user_ids: List[str], start_date: str, end_date: str
    ) -> List[Dict]:
        """
        获取考勤打卡数据。
        POST /checkin/getcheckindata

        Args:
            user_ids: 用户 userid 列表（单次最多 100 人）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            标准化考勤记录列表
        """
        url = f"{self.BASE_URL}/checkin/getcheckindata"

        # 转换日期为 Unix 时间戳
        try:
            start_ts = int(
                datetime.strptime(start_date, "%Y-%m-%d").timestamp()
            )
            end_ts = int(
                datetime.strptime(end_date, "%Y-%m-%d").timestamp()
            ) + 86399  # 当天 23:59:59
        except ValueError as e:
            logger.error(f"[wecom] Invalid date format: {e}")
            return []

        all_records = []
        # 企微限制每次最多 100 个用户
        batch_size = 100
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i : i + batch_size]
            body = {
                "opencheckindatatype": 3,  # 3=全部
                "starttime": start_ts,
                "endtime": end_ts,
                "useridlist": batch,
            }
            try:
                data = await self._api_request("POST", url, json=body)
                records = data.get("checkindata", [])
                for record in records:
                    all_records.append(
                        {
                            "userid": record.get("userid", ""),
                            "checkin_time": record.get("checkin_time", 0),
                            "checkin_type": record.get("checkin_type", ""),
                            "exception_type": record.get("exception_type", ""),
                            "location_title": record.get("location_title", ""),
                            "notes": record.get("notes", ""),
                            "raw": record,
                        }
                    )
            except Exception as e:
                logger.error(f"[wecom] Failed to get attendance for batch: {e}")

        return all_records

    # ── Messaging ─────────────────────────────────────────────────

    async def send_text_message(self, user_id: str, content: str) -> bool:
        """
        发送文本应用消息。
        POST /message/send

        Args:
            user_id: 接收人的 userid（多人用 | 分隔）
            content: 消息文本内容

        Returns:
            发送是否成功
        """
        url = f"{self.BASE_URL}/message/send"
        body = {
            "touser": user_id,
            "msgtype": "text",
            "agentid": self.agent_id,
            "text": {"content": content},
        }
        try:
            await self._api_request("POST", url, json=body)
            logger.info(f"[wecom] Text message sent to {user_id}")
            return True
        except Exception as e:
            logger.error(f"[wecom] Failed to send text message to {user_id}: {e}")
            return False

    async def send_interactive_card(self, user_id: str, card: Dict) -> bool:
        """
        发送互动模板卡片消息（支持审批通知含批准/拒绝按钮）。
        POST /message/send 使用 msgtype="template_card"

        企微模板卡片类型：
        - text_notice: 文本通知
        - news_notice: 图文通知
        - button_interaction: 按钮交互型（审批场景）
        - vote_interaction: 投票型
        - multiple_interaction: 多项交互型

        Args:
            user_id: 接收人 userid
            card: 卡片数据，参考企微模板卡片文档

        Returns:
            发送是否成功
        """
        url = f"{self.BASE_URL}/message/send"
        body = {
            "touser": user_id,
            "msgtype": "template_card",
            "agentid": self.agent_id,
            "template_card": card,
        }
        try:
            await self._api_request("POST", url, json=body)
            logger.info(f"[wecom] Interactive card sent to {user_id}")
            return True
        except Exception as e:
            logger.error(
                f"[wecom] Failed to send interactive card to {user_id}: {e}"
            )
            return False

    # ── OAuth SSO ─────────────────────────────────────────────────

    def get_oauth_url(self, redirect_uri: str, state: str = "") -> str:
        """
        构造企微 OAuth2.0 网页授权链接。

        用户点击后，企微会重定向到 redirect_uri 并附带 code 参数。
        参考文档：https://developer.work.weixin.qq.com/document/path/91022

        Args:
            redirect_uri: 授权回调地址（需 URL 编码）
            state: 防 CSRF 的自定义参数

        Returns:
            完整的 OAuth 授权 URL
        """
        encoded_uri = quote(redirect_uri, safe="")
        return (
            f"https://open.weixin.qq.com/connect/oauth2/authorize"
            f"?appid={self.corp_id}"
            f"&redirect_uri={encoded_uri}"
            f"&response_type=code"
            f"&scope=snsapi_base"
            f"&state={state or 'nexus'}"
            f"&agentid={self.agent_id}"
            f"#wechat_redirect"
        )

    async def get_user_by_auth_code(self, code: str) -> Dict:
        """
        通过 OAuth code 获取用户身份信息。
        GET /auth/getuserinfo?code=xxx

        Args:
            code: OAuth 回调中携带的授权码

        Returns:
            {"userid": "xxx", "user_ticket": "xxx"} 或
            {"openid": "xxx"}（外部联系人）
        """
        url = f"{self.BASE_URL}/auth/getuserinfo"
        try:
            data = await self._api_request("GET", url, params={"code": code})
            result = {
                "userid": data.get("userid", data.get("UserId", "")),
                "user_ticket": data.get("user_ticket", ""),
                "openid": data.get("openid", data.get("OpenId", "")),
            }
            logger.info(f"[wecom] OAuth user resolved: {result.get('userid', 'external')}")
            return result
        except Exception as e:
            logger.error(f"[wecom] Failed to get user by auth code: {e}")
            raise

    # ── Card Callback Update ──────────────────────────────────────

    async def update_template_card(
        self, user_id: str, response_code: str, card: Dict
    ) -> bool:
        """
        更新模板卡片内容（用户点击按钮后更新卡片状态）。
        POST /message/update_template_card

        Args:
            user_id: 用户 userid
            response_code: 卡片回调中的 response_code
            card: 更新后的卡片数据

        Returns:
            更新是否成功
        """
        url = f"{self.BASE_URL}/message/update_template_card"
        body = {
            "userids": [user_id],
            "agentid": self.agent_id,
            "response_code": response_code,
            "template_card": card,
        }
        try:
            await self._api_request("POST", url, json=body)
            return True
        except Exception as e:
            logger.error(f"[wecom] Failed to update template card: {e}")
            return False

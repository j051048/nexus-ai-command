"""
钉钉完整 API 客户端

基于钉钉开放平台 API 实现完整功能：
- Token 获取与管理（新版 OAuth2 接口）
- 通讯录同步（部门 + 用户列表）
- 考勤打卡数据拉取
- 工作通知消息推送（文本 + 互动卡片）
- OAuth2.0 授权登录（SSO）

官方文档：https://open.dingtalk.com/document/
注意：钉钉新版 API 用 Header 传 token，旧版用 query param。
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.services.im_platform.base_client import IMPlatformClient

logger = logging.getLogger(__name__)


class DingtalkClient(IMPlatformClient):
    """
    钉钉完整 API 客户端。

    钉钉 API 特点：
    - 新版 API (api.dingtalk.com): Header 传 token (x-acs-dingtalk-access-token)
    - 旧版 API (oapi.dingtalk.com): query param 传 access_token
    - Token 通过 POST body 获取（非 query param）
    """

    AUTH_URL = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
    API_URL = "https://oapi.dingtalk.com"
    NEW_API_URL = "https://api.dingtalk.com"

    def __init__(self, app_key: str, app_secret: str, agent_id: str = ""):
        """
        初始化钉钉客户端。

        Args:
            app_key: 应用的 AppKey
            app_secret: 应用的 AppSecret
            agent_id: 应用的 AgentId（发送工作通知时需要）
        """
        super().__init__("dingtalk")
        self.app_key = app_key
        self.app_secret = app_secret
        self.agent_id = agent_id

    # ── Token ─────────────────────────────────────────────────────

    async def _fetch_access_token(self) -> dict[str, Any]:
        """
        获取钉钉 access_token。
        POST https://api.dingtalk.com/v1.0/oauth2/accessToken
        Body: {"appKey": "xxx", "appSecret": "xxx"}

        Returns:
            {"access_token": "xxx", "expires_in": 7200}
        """
        client = await self._get_http_client()
        body = {
            "appKey": self.app_key,
            "appSecret": self.app_secret,
        }

        response = await client.post(
            self.AUTH_URL,
            json=body,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        if "accessToken" not in data:
            raise Exception(
                f"Dingtalk gettoken error: {data.get('message', 'unknown')}"
            )

        return {
            "access_token": data["accessToken"],
            "expires_in": data.get("expireIn", 7200),
        }

    # ── API 请求覆盖 ─────────────────────────────────────────────

    async def _api_request(self, method: str, url: str, **kwargs) -> dict:
        """
        覆盖基类: 钉钉旧版 API 用 query param, 新版 API 用 header。

        自动判断: 如果 url 以 api.dingtalk.com 开头则用 header，
        否则（oapi.dingtalk.com）用 query param。
        """
        token = await self.get_access_token()
        client = await self._get_http_client()

        if url.startswith(self.NEW_API_URL):
            # 新版 API: token 通过 Header 传递
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["x-acs-dingtalk-access-token"] = token
            kwargs["headers"]["Content-Type"] = "application/json"
        else:
            # 旧版 API: token 通过 query param 传递
            if "params" not in kwargs:
                kwargs["params"] = {}
            kwargs["params"]["access_token"] = token

        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[dingtalk] HTTP {e.response.status_code} "
                f"for {method} {url}: {e.response.text[:200]}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"[dingtalk] Request error for {method} {url}: {e}")
            raise

        # 旧版 API 错误码检查
        errcode = data.get("errcode")
        if errcode is not None and errcode != 0:
            errmsg = data.get("errmsg", "unknown error")
            logger.error(
                f"[dingtalk] API business error: "
                f"errcode={errcode}, errmsg={errmsg}, url={url}"
            )
            raise Exception(
                f"dingtalk API error (code={errcode}): {errmsg}"
            )

        # 新版 API 错误检查
        if "code" in data and data["code"] != "0" and data.get("code") is not None:
            message = data.get("message", "unknown error")
            logger.error(
                f"[dingtalk] New API error: code={data['code']}, "
                f"message={message}, url={url}"
            )
            raise Exception(
                f"dingtalk API error (code={data['code']}): {message}"
            )

        return data

    # ── Contact / Directory ───────────────────────────────────────

    async def get_departments(self) -> list[dict]:
        """
        获取部门列表。
        POST /topapi/v2/department/listsub

        Returns:
            [{"id": "1", "name": "总部", "parentid": "0"}, ...]
        """
        url = f"{self.API_URL}/topapi/v2/department/listsub"
        all_departments = []

        # 递归获取所有部门（从根部门 1 开始）
        dept_queue = ["1"]
        visited = set()

        while dept_queue:
            dept_id = dept_queue.pop(0)
            if dept_id in visited:
                continue
            visited.add(dept_id)

            try:
                data = await self._api_request(
                    "POST", url, json={"dept_id": int(dept_id)}
                )
                sub_depts = data.get("result", [])
                for dept in sub_depts:
                    dept_info = {
                        "id": str(dept.get("dept_id", "")),
                        "name": dept.get("name", ""),
                        "parentid": str(dept_id),
                        "order": dept.get("order", 0),
                    }
                    all_departments.append(dept_info)
                    dept_queue.append(str(dept.get("dept_id", "")))
            except Exception as e:
                logger.error(
                    f"[dingtalk] Failed to get sub departments for {dept_id}: {e}"
                )

        return all_departments

    async def get_department_users(self, department_id: str) -> list[dict]:
        """
        获取部门下的用户列表。
        POST /topapi/v2/user/list

        Args:
            department_id: 部门 ID

        Returns:
            [{"userid": "xxx", "name": "张三", "mobile": "138...", ...}, ...]
        """
        url = f"{self.API_URL}/topapi/v2/user/list"
        all_users = []
        cursor = 0
        has_more = True

        while has_more:
            body = {
                "dept_id": int(department_id),
                "cursor": cursor,
                "size": 100,
            }
            try:
                data = await self._api_request("POST", url, json=body)
                result = data.get("result", {})
                user_list = result.get("list", [])

                for user in user_list:
                    all_users.append(
                        {
                            "userid": user.get("userid", ""),
                            "name": user.get("name", ""),
                            "mobile": user.get("mobile", ""),
                            "email": user.get("email", ""),
                            "department": user.get("dept_id_list", []),
                            "position": user.get("title", ""),
                            "avatar": user.get("avatar", ""),
                            "unionid": user.get("unionid", ""),
                        }
                    )

                has_more = result.get("has_more", False)
                cursor = result.get("next_cursor", 0)
            except Exception as e:
                logger.error(
                    f"[dingtalk] Failed to get users for dept {department_id}: {e}"
                )
                break

        return all_users

    # ── Attendance ────────────────────────────────────────────────

    async def get_attendance_records(
        self, user_ids: list[str], start_date: str, end_date: str
    ) -> list[dict]:
        """
        获取考勤记录。
        POST /attendance/list

        Args:
            user_ids: 用户 userid 列表（单次最多 50 人）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            标准化考勤记录列表
        """
        url = f"{self.API_URL}/attendance/list"

        # 钉钉日期格式: "yyyy-MM-dd HH:mm:ss"
        work_date_from = f"{start_date} 00:00:00"
        work_date_to = f"{end_date} 23:59:59"

        all_records = []
        batch_size = 50

        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i : i + batch_size]
            offset = 0
            has_more = True

            while has_more:
                body = {
                    "workDateFrom": work_date_from,
                    "workDateTo": work_date_to,
                    "userIdList": batch,
                    "offset": offset,
                    "limit": 50,
                }
                try:
                    data = await self._api_request("POST", url, json=body)
                    records = data.get("recordresult", [])

                    for record in records:
                        all_records.append(
                            {
                                "userid": record.get("userId", ""),
                                "checkin_time": record.get("userCheckTime", 0),
                                "checkin_type": record.get("checkType", ""),
                                "time_result": record.get("timeResult", ""),
                                "location_result": record.get("locationResult", ""),
                                "work_date": record.get("workDate", ""),
                                "raw": record,
                            }
                        )

                    has_more = data.get("hasMore", False)
                    offset += len(records)
                except Exception as e:
                    logger.error(
                        f"[dingtalk] Failed to get attendance for batch: {e}"
                    )
                    has_more = False

        return all_records

    # ── Messaging ─────────────────────────────────────────────────

    async def send_text_message(self, user_id: str, content: str) -> bool:
        """
        发送工作通知文本消息。
        POST /topapi/message/corpconversation/asyncsend_v2

        Args:
            user_id: 接收人 userid（多人用逗号分隔）
            content: 消息文本

        Returns:
            发送是否成功
        """
        url = f"{self.API_URL}/topapi/message/corpconversation/asyncsend_v2"
        body = {
            "agent_id": self.agent_id,
            "userid_list": user_id,
            "msg": {
                "msgtype": "text",
                "text": {"content": content},
            },
        }
        try:
            await self._api_request("POST", url, json=body)
            logger.info(f"[dingtalk] Text message sent to {user_id}")
            return True
        except Exception as e:
            logger.error(
                f"[dingtalk] Failed to send text message to {user_id}: {e}"
            )
            return False

    async def send_interactive_card(self, user_id: str, card: dict) -> bool:
        """
        发送互动卡片（ActionCard）工作通知。
        POST /topapi/message/corpconversation/asyncsend_v2

        ActionCard 支持：
        - 整体跳转（单按钮）
        - 独立跳转（多按钮，如审批的批准/拒绝）

        Args:
            user_id: 接收人 userid
            card: ActionCard 数据

        Returns:
            发送是否成功
        """
        url = f"{self.API_URL}/topapi/message/corpconversation/asyncsend_v2"
        body = {
            "agent_id": self.agent_id,
            "userid_list": user_id,
            "msg": {
                "msgtype": "action_card",
                "action_card": card,
            },
        }
        try:
            await self._api_request("POST", url, json=body)
            logger.info(f"[dingtalk] Interactive card sent to {user_id}")
            return True
        except Exception as e:
            logger.error(
                f"[dingtalk] Failed to send interactive card to {user_id}: {e}"
            )
            return False

    # ── OAuth SSO ─────────────────────────────────────────────────

    def get_oauth_url(self, redirect_uri: str, state: str = "") -> str:
        """
        构造钉钉 OAuth2.0 授权链接。

        参考文档：https://open.dingtalk.com/document/orgapp/tutorial-obtaining-user-personal-information

        Args:
            redirect_uri: 授权回调地址
            state: 防 CSRF 参数

        Returns:
            完整的 OAuth 授权 URL
        """
        encoded_uri = quote(redirect_uri, safe="")
        return (
            f"https://login.dingtalk.com/oauth2/auth"
            f"?redirect_uri={encoded_uri}"
            f"&response_type=code"
            f"&client_id={self.app_key}"
            f"&scope=openid"
            f"&state={state or 'nexus'}"
            f"&prompt=consent"
        )

    async def get_user_by_auth_code(self, code: str) -> dict:
        """
        通过 OAuth code 获取用户信息。

        流程：
        1. 用 code 换取 user access token
        2. 用 user access token 获取用户信息

        Args:
            code: OAuth 回调中的授权码

        Returns:
            {"userid": "xxx", "name": "xxx", "unionid": "xxx", ...}
        """
        client = await self._get_http_client()

        # Step 1: 用 code 换取 user access token
        token_url = f"{self.NEW_API_URL}/v1.0/oauth2/userAccessToken"
        token_body = {
            "clientId": self.app_key,
            "clientSecret": self.app_secret,
            "code": code,
            "grantType": "authorization_code",
        }

        try:
            token_resp = await client.post(
                token_url,
                json=token_body,
                headers={"Content-Type": "application/json"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            user_access_token = token_data.get("accessToken", "")

            if not user_access_token:
                raise Exception(
                    f"Failed to get user access token: {token_data}"
                )

            # Step 2: 获取用户信息
            user_url = f"{self.NEW_API_URL}/v1.0/contact/users/me"
            user_resp = await client.get(
                user_url,
                headers={
                    "x-acs-dingtalk-access-token": user_access_token,
                },
            )
            user_resp.raise_for_status()
            user_data = user_resp.json()

            # Step 3: 通过 unionId 获取 userid
            userid = ""
            union_id = user_data.get("unionId", "")
            if union_id:
                try:
                    userid_url = (
                        f"{self.API_URL}/topapi/user/getbyunionid"
                    )
                    uid_data = await self._api_request(
                        "POST", userid_url, json={"unionid": union_id}
                    )
                    userid = uid_data.get("result", {}).get("userid", "")
                except Exception:
                    logger.warning(
                        "[dingtalk] Could not resolve userid from unionId"
                    )

            result = {
                "userid": userid,
                "name": user_data.get("nick", ""),
                "unionid": union_id,
                "openid": user_data.get("openId", ""),
                "email": user_data.get("email", ""),
                "mobile": user_data.get("mobile", ""),
                "avatar": user_data.get("avatarUrl", ""),
            }
            logger.info(
                f"[dingtalk] OAuth user resolved: userid={result['userid']}"
            )
            return result

        except Exception as e:
            logger.error(f"[dingtalk] Failed to get user by auth code: {e}")
            raise

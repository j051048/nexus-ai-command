"""
飞书完整 API 客户端

基于飞书开放平台 API 实现完整功能：
- Token 获取与管理（tenant_access_token）
- 通讯录同步（部门 + 用户列表）
- 考勤打卡数据拉取
- 消息发送（文本 + 互动消息卡片）
- OAuth2.0 授权登录（SSO）

官方文档：https://open.feishu.cn/document/
注意：飞书 API 通过 Header "Authorization: Bearer {token}" 传 token。
"""

import json as json_module
import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.services.im_platform.base_client import IMPlatformClient

logger = logging.getLogger(__name__)


class FeishuClient(IMPlatformClient):
    """
    飞书完整 API 客户端。

    飞书 API 特点：
    - tenant_access_token 通过 POST /auth/v3/tenant_access_token/internal 获取
    - 所有 API 通过 Header "Authorization: Bearer {token}" 传 token
    - 响应格式: {"code": 0, "msg": "success", "data": {...}}
    """

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str, app_secret: str):
        """
        初始化飞书客户端。

        Args:
            app_id: 应用 App ID
            app_secret: 应用 App Secret
        """
        super().__init__("feishu")
        self.app_id = app_id
        self.app_secret = app_secret

    # ── Token ─────────────────────────────────────────────────────

    async def _fetch_access_token(self) -> dict[str, Any]:
        """
        获取飞书 tenant_access_token。
        POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
        Body: {"app_id": "xxx", "app_secret": "xxx"}

        Returns:
            {"access_token": "xxx", "expires_in": 7200}
        """
        client = await self._get_http_client()
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        body = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }

        response = await client.post(
            url,
            json=body,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code", -1) != 0:
            raise Exception(
                f"Feishu gettoken error: {data.get('msg', 'unknown')}"
            )

        return {
            "access_token": data["tenant_access_token"],
            "expires_in": data.get("expire", 7200),
        }

    # ── API 请求覆盖 ─────────────────────────────────────────────

    async def _api_request(self, method: str, url: str, **kwargs) -> dict:
        """
        覆盖基类: 飞书通过 Header "Authorization: Bearer {token}" 传 token。
        飞书响应格式: {"code": 0, "msg": "success", "data": {...}}
        """
        token = await self.get_access_token()
        client = await self._get_http_client()

        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"]["Authorization"] = f"Bearer {token}"
        kwargs["headers"]["Content-Type"] = "application/json; charset=utf-8"

        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[feishu] HTTP {e.response.status_code} "
                f"for {method} {url}: {e.response.text[:200]}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"[feishu] Request error for {method} {url}: {e}")
            raise

        # 飞书业务错误码检查
        code = data.get("code", 0)
        if code != 0:
            msg = data.get("msg", "unknown error")
            logger.error(
                f"[feishu] API business error: code={code}, msg={msg}, url={url}"
            )
            raise Exception(f"feishu API error (code={code}): {msg}")

        return data

    # ── Contact / Directory ───────────────────────────────────────

    async def get_departments(self) -> list[dict]:
        """
        获取部门列表。
        GET /contact/v3/departments

        Returns:
            [{"id": "xxx", "name": "总部", "parentid": "0"}, ...]
        """
        url = f"{self.BASE_URL}/contact/v3/departments"
        all_departments = []
        page_token = ""
        has_more = True

        while has_more:
            params = {
                "page_size": 50,
                "parent_department_id": "0",
                "fetch_child": "true",
            }
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._api_request("GET", url, params=params)
                items = data.get("data", {}).get("items", [])

                for dept in items:
                    all_departments.append(
                        {
                            "id": dept.get("department_id", dept.get("open_department_id", "")),
                            "name": dept.get("name", ""),
                            "parentid": dept.get("parent_department_id", "0"),
                            "order": dept.get("order", "0"),
                            "open_department_id": dept.get("open_department_id", ""),
                        }
                    )

                has_more = data.get("data", {}).get("has_more", False)
                page_token = data.get("data", {}).get("page_token", "")
            except Exception as e:
                logger.error(f"[feishu] Failed to get departments: {e}")
                break

        return all_departments

    async def get_department_users(self, department_id: str) -> list[dict]:
        """
        获取部门下的用户列表。
        GET /contact/v3/users?department_id=xxx

        Args:
            department_id: 部门 ID

        Returns:
            [{"userid": "xxx", "name": "张三", "mobile": "138...", ...}, ...]
        """
        url = f"{self.BASE_URL}/contact/v3/users"
        all_users = []
        page_token = ""
        has_more = True

        while has_more:
            params = {
                "department_id": department_id,
                "page_size": 50,
            }
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._api_request("GET", url, params=params)
                items = data.get("data", {}).get("items", [])

                for user in items:
                    all_users.append(
                        {
                            "userid": user.get("user_id", user.get("open_id", "")),
                            "name": user.get("name", ""),
                            "mobile": user.get("mobile", ""),
                            "email": user.get("email", ""),
                            "department": user.get("department_ids", []),
                            "position": user.get("job_title", ""),
                            "avatar": user.get("avatar", {}).get("avatar_72", ""),
                            "open_id": user.get("open_id", ""),
                            "union_id": user.get("union_id", ""),
                        }
                    )

                has_more = data.get("data", {}).get("has_more", False)
                page_token = data.get("data", {}).get("page_token", "")
            except Exception as e:
                logger.error(
                    f"[feishu] Failed to get users for dept {department_id}: {e}"
                )
                break

        return all_users

    # ── Attendance ────────────────────────────────────────────────

    async def get_attendance_records(
        self, user_ids: list[str], start_date: str, end_date: str
    ) -> list[dict]:
        """
        获取考勤打卡数据。
        POST /attendance/v1/user_tasks/query

        Args:
            user_ids: 用户 user_id 列表
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            标准化考勤记录列表
        """
        url = f"{self.BASE_URL}/attendance/v1/user_tasks/query"
        all_records = []

        # 飞书日期格式: 20060102 (yyyyMMdd)
        try:
            start_formatted = start_date.replace("-", "")
            end_formatted = end_date.replace("-", "")
        except Exception as e:
            logger.error(f"[feishu] Invalid date format: {e}")
            return []

        # 每次最多 50 个用户
        batch_size = 50
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i : i + batch_size]
            body = {
                "user_ids": batch,
                "check_date_from": start_formatted,
                "check_date_to": end_formatted,
            }
            params = {"employee_type": "employee_id"}

            try:
                data = await self._api_request(
                    "POST", url, json=body, params=params
                )
                task_list = data.get("data", {}).get("user_task_results", [])

                for task in task_list:
                    records = task.get("records", [])
                    user_id = task.get("user_id", "")
                    for record in records:
                        all_records.append(
                            {
                                "userid": user_id,
                                "checkin_time": record.get("check_time", ""),
                                "checkin_type": record.get("check_type", ""),
                                "location_name": record.get("location_name", ""),
                                "check_result": record.get("check_result", ""),
                                "work_date": task.get("day", ""),
                                "raw": record,
                            }
                        )
            except Exception as e:
                logger.error(
                    f"[feishu] Failed to get attendance for batch: {e}"
                )

        return all_records

    # ── Messaging ─────────────────────────────────────────────────

    async def send_text_message(self, user_id: str, content: str) -> bool:
        """
        发送文本消息。
        POST /im/v1/messages?receive_id_type=user_id

        Args:
            user_id: 接收人的 user_id
            content: 消息文本

        Returns:
            发送是否成功
        """
        url = f"{self.BASE_URL}/im/v1/messages"
        params = {"receive_id_type": "user_id"}
        body = {
            "receive_id": user_id,
            "msg_type": "text",
            "content": json_module.dumps({"text": content}),
        }
        try:
            await self._api_request("POST", url, json=body, params=params)
            logger.info(f"[feishu] Text message sent to {user_id}")
            return True
        except Exception as e:
            logger.error(
                f"[feishu] Failed to send text message to {user_id}: {e}"
            )
            return False

    async def send_interactive_card(self, user_id: str, card: dict) -> bool:
        """
        发送互动消息卡片（Interactive Card）。
        POST /im/v1/messages?receive_id_type=user_id

        飞书互动卡片支持按钮、表单等交互元素，适用于审批通知等场景。

        Args:
            user_id: 接收人 user_id
            card: 卡片 JSON 数据（飞书 Interactive Card 格式）

        Returns:
            发送是否成功
        """
        url = f"{self.BASE_URL}/im/v1/messages"
        params = {"receive_id_type": "user_id"}
        body = {
            "receive_id": user_id,
            "msg_type": "interactive",
            "content": json_module.dumps(card),
        }
        try:
            await self._api_request("POST", url, json=body, params=params)
            logger.info(f"[feishu] Interactive card sent to {user_id}")
            return True
        except Exception as e:
            logger.error(
                f"[feishu] Failed to send interactive card to {user_id}: {e}"
            )
            return False

    # ── OAuth SSO ─────────────────────────────────────────────────

    def get_oauth_url(self, redirect_uri: str, state: str = "") -> str:
        """
        构造飞书 OAuth 授权链接。

        参考文档：https://open.feishu.cn/document/common-capabilities/sso/api/get-oauth-code

        Args:
            redirect_uri: 授权回调地址
            state: 防 CSRF 参数

        Returns:
            完整的 OAuth 授权 URL
        """
        encoded_uri = quote(redirect_uri, safe="")
        return (
            f"{self.BASE_URL}/authen/v1/authorize"
            f"?app_id={self.app_id}"
            f"&redirect_uri={encoded_uri}"
            f"&state={state or 'nexus'}"
        )

    async def get_user_by_auth_code(self, code: str) -> dict:
        """
        通过 OAuth code 获取用户信息。

        流程：
        1. 用 code 换取 user_access_token (POST /authen/v1/oidc/access_token)
        2. 用 user_access_token 获取用户信息 (GET /authen/v1/user_info)

        Args:
            code: OAuth 回调中的授权码

        Returns:
            {"userid": "xxx", "name": "xxx", "open_id": "xxx", ...}
        """
        client = await self._get_http_client()

        # Step 1: 用 code 换取 user_access_token
        token = await self.get_access_token()
        token_url = f"{self.BASE_URL}/authen/v1/oidc/access_token"
        token_body = {
            "grant_type": "authorization_code",
            "code": code,
        }

        try:
            token_resp = await client.post(
                token_url,
                json=token_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            if token_data.get("code", -1) != 0:
                raise Exception(
                    f"Failed to get user access token: {token_data.get('msg')}"
                )

            user_access_token = token_data.get("data", {}).get(
                "access_token", ""
            )

            if not user_access_token:
                raise Exception("Empty user access token returned")

            # Step 2: 获取用户信息
            user_url = f"{self.BASE_URL}/authen/v1/user_info"
            user_resp = await client.get(
                user_url,
                headers={
                    "Authorization": f"Bearer {user_access_token}",
                },
            )
            user_resp.raise_for_status()
            user_data = user_resp.json()

            if user_data.get("code", -1) != 0:
                raise Exception(
                    f"Failed to get user info: {user_data.get('msg')}"
                )

            info = user_data.get("data", {})
            result = {
                "userid": info.get("user_id", ""),
                "name": info.get("name", ""),
                "open_id": info.get("open_id", ""),
                "union_id": info.get("union_id", ""),
                "email": info.get("email", ""),
                "mobile": info.get("mobile", ""),
                "avatar": info.get("avatar_url", ""),
                "tenant_key": info.get("tenant_key", ""),
            }
            logger.info(
                f"[feishu] OAuth user resolved: userid={result['userid']}"
            )
            return result

        except Exception as e:
            logger.error(f"[feishu] Failed to get user by auth code: {e}")
            raise

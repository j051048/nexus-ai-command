"""
IM 平台客户端抽象基类

定义企微/钉钉/飞书统一接口，包含：
- Token 自动管理（缓存 + 提前 5 分钟刷新）
- 通讯录（部门/用户）
- 考勤数据
- 消息发送（文本 + 互动卡片）
- OAuth SSO
- 带 token 的 API 请求封装
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class IMPlatformClient(ABC):
    """
    IM 平台客户端抽象基类。
    定义企微/钉钉/飞书统一接口。

    子类需实现所有 @abstractmethod 方法，并可覆盖 _api_request
    以适配不同平台的 token 传递方式（query param vs header）。
    """

    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self._access_token: str | None = None
        self._token_expires_at: float = 0
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端（复用连接池）"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._http_client

    async def close(self):
        """关闭 HTTP 客户端，释放连接资源"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
        logger.debug(f"[{self.platform_name}] HTTP client closed")

    # ── Token Management ──────────────────────────────────────────

    async def get_access_token(self) -> str:
        """
        获取 access_token，自动缓存和刷新。
        在过期前 300 秒（5 分钟）主动刷新，避免请求失败。
        """
        if self._access_token and time.time() < self._token_expires_at - 300:
            return self._access_token

        logger.info(f"[{self.platform_name}] Refreshing access token...")
        try:
            token_data = await self._fetch_access_token()
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 7200)
            self._token_expires_at = time.time() + expires_in
            logger.info(
                f"[{self.platform_name}] Access token refreshed, expires in {expires_in}s"
            )
            return self._access_token
        except Exception as e:
            logger.error(f"[{self.platform_name}] Failed to refresh token: {e}")
            raise

    @abstractmethod
    async def _fetch_access_token(self) -> dict[str, Any]:
        """
        子类实现: 从平台 API 获取 access_token。

        Returns:
            Dict 包含 "access_token" 和 "expires_in" 字段
        """
        ...

    # ── Contact / Directory ───────────────────────────────────────

    @abstractmethod
    async def get_departments(self) -> list[dict]:
        """
        获取部门列表。

        Returns:
            [{"id": "1", "name": "总部", "parentid": "0"}, ...]
        """
        ...

    @abstractmethod
    async def get_department_users(self, department_id: str) -> list[dict]:
        """
        获取部门下的用户列表。

        Args:
            department_id: 平台部门 ID

        Returns:
            [{"userid": "xxx", "name": "张三", "mobile": "138...", ...}, ...]
        """
        ...

    # ── Attendance ────────────────────────────────────────────────

    @abstractmethod
    async def get_attendance_records(
        self, user_ids: list[str], start_date: str, end_date: str
    ) -> list[dict]:
        """
        获取考勤打卡数据。

        Args:
            user_ids: 用户 ID 列表
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            标准化考勤记录列表
        """
        ...

    # ── Messaging ─────────────────────────────────────────────────

    @abstractmethod
    async def send_text_message(self, user_id: str, content: str) -> bool:
        """
        发送文本消息给指定用户。

        Args:
            user_id: 平台用户 ID
            content: 消息文本内容

        Returns:
            发送是否成功
        """
        ...

    @abstractmethod
    async def send_interactive_card(self, user_id: str, card: dict) -> bool:
        """
        发送互动消息卡片（含按钮，如审批通知）。

        Args:
            user_id: 平台用户 ID
            card: 卡片数据（格式因平台而异）

        Returns:
            发送是否成功
        """
        ...

    # ── OAuth SSO ─────────────────────────────────────────────────

    @abstractmethod
    def get_oauth_url(self, redirect_uri: str, state: str = "") -> str:
        """
        生成 OAuth 授权链接，供前端跳转。

        Args:
            redirect_uri: 授权回调 URI
            state: 防 CSRF 状态参数

        Returns:
            完整的 OAuth 授权 URL
        """
        ...

    @abstractmethod
    async def get_user_by_auth_code(self, code: str) -> dict:
        """
        通过 OAuth 授权码获取用户信息。

        Args:
            code: 授权回调中的 code 参数

        Returns:
            用户信息 Dict，至少包含 userid 字段
        """
        ...

    # ── Helper ────────────────────────────────────────────────────

    async def _api_request(self, method: str, url: str, **kwargs) -> dict:
        """
        带 token 的 API 请求封装。

        默认实现将 token 添加到 query params（企微风格）。
        钉钉/飞书子类覆盖此方法，改用 header 传 token。

        Args:
            method: HTTP 方法 (GET/POST/PUT/DELETE)
            url: 完整的 API URL
            **kwargs: 传递给 httpx.request 的额外参数

        Returns:
            API 响应 JSON 数据

        Raises:
            Exception: API 返回业务错误码时抛出
        """
        token = await self.get_access_token()
        client = await self._get_http_client()

        # 企微默认: token 通过 query param 传递
        if "params" not in kwargs:
            kwargs["params"] = {}
        kwargs["params"]["access_token"] = token

        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[{self.platform_name}] HTTP {e.response.status_code} for {method} {url}: {e.response.text[:200]}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(
                f"[{self.platform_name}] Request error for {method} {url}: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"[{self.platform_name}] Unexpected error for {method} {url}: {e}"
            )
            raise

        # 检查业务错误码（企微标准: errcode == 0 表示成功）
        errcode = data.get("errcode", 0)
        if errcode != 0:
            errmsg = data.get("errmsg", "unknown error")
            logger.error(
                f"[{self.platform_name}] API business error: errcode={errcode}, errmsg={errmsg}, url={url}"
            )
            raise Exception(
                f"{self.platform_name} API error (code={errcode}): {errmsg}"
            )

        return data

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} platform={self.platform_name}>"

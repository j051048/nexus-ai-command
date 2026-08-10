"""
P3 Enhancement: Database Connection Module

Provides a lightweight Supabase client wrapper using PostgREST.
Falls back gracefully when database is not configured.
"""

import hashlib
import logging
import os

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Base credentials
url: str = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_URI", "")
key: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# G5 fix: Global httpx client for PostgREST logic (Force HTTP/1.1)
# We manage this manually inside MiniSupabaseClient since postgrest-py encapsulates its own client.

try:
    from collections import OrderedDict  # noqa: F401
    from contextvars import ContextVar

    from postgrest import AsyncPostgrestClient

    # P1-3修复: 使用ContextVar替代全局字典,避免线程安全问题
    _request_scoped_clients: ContextVar[dict] = ContextVar("scoped_clients", default={})
    _SCOPED_CLIENT_CACHE_MAX = 200

    class MiniSupabaseClient:
        """
        Lightweight async Supabase client wrapper.
        Uses PostgREST directly for better compatibility.
        """

        def __init__(self, url: str, key: str, token: str = None):
            # PostgREST expects base URL. Supabase URL usually ends with .co, needing /rest/v1 for PostgREST
            base_url = f"{url.rstrip('/')}/rest/v1"
            headers = {
                "apikey": key,
                "Authorization": f"Bearer {token or key}",
                "Content-Type": "application/json",
            }
            # Connection pool configuration with timeout
            timeout = httpx.Timeout(30.0, connect=10.0)

            self.client = AsyncPostgrestClient(
                base_url, headers=headers, timeout=timeout
            )
            self._url = url
            self._key = key

        def table(self, name: str):
            return self.client.from_(name)

        def rpc(self, name: str, params: dict):
            return self.client.rpc(name, params)

        @property
        def is_configured(self) -> bool:
            return bool(self._url) and bool(self.client)

        def get_scoped_client(self, token: str):
            # P1-3修复: 使用ContextVar获取请求级别的缓存
            cache = _request_scoped_clients.get()
            cache_key = hashlib.sha256(token.encode()).hexdigest() if token else ""

            if cache_key in cache:
                return cache[cache_key]

            # 限制缓存大小
            if len(cache) >= _SCOPED_CLIENT_CACHE_MAX:
                cache.clear()

            client = MiniSupabaseClient(self._url, self._key, token)
            cache[cache_key] = client
            _request_scoped_clients.set(cache)
            return client

        def get_org_filtered_client(self, org_id: str):
            return OrgFilteredClient(self, org_id)

    class _OrgScopedRequestBuilder:
        """Proxy that injects .eq("organization_id", org_id) after .select()/.update()/.delete()."""

        def __init__(self, builder, org_id: str):
            self._builder = builder
            self._org_id = org_id

        def select(self, *args, **kwargs):
            return self._builder.select(*args, **kwargs).eq(
                "organization_id", self._org_id
            )

        def insert(self, *args, **kwargs):
            return self._builder.insert(*args, **kwargs)

        def upsert(self, *args, **kwargs):
            return self._builder.upsert(*args, **kwargs)

        def update(self, *args, **kwargs):
            return self._builder.update(*args, **kwargs).eq(
                "organization_id", self._org_id
            )

        def delete(self, *args, **kwargs):
            return self._builder.delete(*args, **kwargs).eq(
                "organization_id", self._org_id
            )

        def __getattr__(self, name):
            return getattr(self._builder, name)

    class OrgFilteredClient:
        _ORG_TABLES = {
            "users",
            "documents",
            "document_embeddings",
            "sales_leads",
            "sales_metrics",
            "approval_requests",
            "projects",
            "departments",
            "notifications",
            "oa_tasks",
            "oa_leave_requests",
            "oa_meeting_bookings",
            "oa_meeting_rooms",
            "oa_work_handovers",
            "business_clue",
            "clue_follow_up",
            "vmd_agent_config",
            "vmd_main_task",
            "vmd_sub_task",
            "vmd_task_audit_record",
            "vmd_reports",
            "vmd_compliance",
            "vmd_compliance_issue",
            "ai_settings",
            "conversation_memories",
            "org_memories",
            "chat_sessions",
            "chat_messages",
            "contracts",
            "competitors",
            "knowledge_graph_triples",
            "entity_aliases",
            "agent_traces",
            "agent_runs",
            "agent_tool_calls",
            "agent_events",
            "semantic_cache",
            "webhook_subscriptions",
            "installed_plugins",
            "work_orders",
            "assets",
            "certificates",
            "inventory",
            "pending_confirmations",
            "artifact_generation_jobs",
            "organization_activation_state",
        }

        def __init__(self, inner: "MiniSupabaseClient", org_id: str):
            self._inner = inner
            self._org_id = org_id

        def table(self, name: str):
            builder = self._inner.table(name)
            if name in self._ORG_TABLES:
                return _OrgScopedRequestBuilder(builder, self._org_id)
            return builder

        def rpc(self, name: str, params: dict):
            if "p_org_id" not in params and "organization_id" not in params:
                params = {**params, "p_org_id": self._org_id}
            return self._inner.rpc(name, params)

        @property
        def is_configured(self) -> bool:
            return self._inner.is_configured

        def get_scoped_client(self, token: str):
            return self._inner.get_scoped_client(token)

        def get_org_filtered_client(self, org_id: str):
            return OrgFilteredClient(self._inner, org_id)

    if not url or not key:
        logger.warning(
            "SUPABASE_URL or SUPABASE_SERVICE_KEY not set. Database features disabled."
        )
        supabase = None
    else:
        supabase = MiniSupabaseClient(url, key)
        logger.info("Database client (Mini) initialized successfully")

except ImportError as e:
    logger.error(f"Failed to import postgrest: {e}")
    supabase = None
except Exception as e:
    logger.error(f"Failed to initialize Supabase wrapper: {e}")
    supabase = None

"""
P3 Enhancement: Database Connection Module

Provides a lightweight Supabase client wrapper using PostgREST.
Falls back gracefully when database is not configured.
"""

import os
import httpx
import logging
import hashlib
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Base credentials
url: str = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_URI", "")
key: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# G5 fix: Global httpx client for PostgREST logic (Force HTTP/1.1)
# We manage this manually inside MiniSupabaseClient since postgrest-py encapsulates its own client.

try:
    from collections import OrderedDict
    from postgrest import AsyncPostgrestClient

    _scoped_client_cache: OrderedDict = OrderedDict()
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
            # G5 Optimization: Force HTTP/1.1 by passing a custom timeout and letting it default
            # Actually, to truly force HTTP/1.1 we would need to pass a client, but AsyncPostgrestClient
            # doesn't make this easy in all versions. We'll set a healthy timeout.
            self.client = AsyncPostgrestClient(base_url, headers=headers, timeout=30)
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
            cache_key = hashlib.sha256(token.encode()).hexdigest() if token else ""
            if cache_key in _scoped_client_cache:
                _scoped_client_cache.move_to_end(cache_key)
                return _scoped_client_cache[cache_key]

            while len(_scoped_client_cache) >= _SCOPED_CLIENT_CACHE_MAX:
                _scoped_client_cache.popitem(last=False)

            client = MiniSupabaseClient(self._url, self._key, token)
            _scoped_client_cache[cache_key] = client
            return client

        def get_org_filtered_client(self, org_id: str):
            return OrgFilteredClient(self, org_id)

    class OrgFilteredClient:
        _ORG_TABLES = {
            "users", "documents", "document_embeddings", "sales_leads", "sales_metrics",
            "approval_requests", "projects", "departments", "notifications", "oa_tasks",
            "ai_settings", "conversation_memories", "org_memories", "chat_sessions",
            "chat_messages", "contracts", "competitors", "knowledge_graph_triples",
            "entity_aliases", "agent_traces", "tenant_credits", "semantic_cache",
            "webhook_subscriptions", "installed_plugins", "vmd_main_task", "vmd_sub_task",
            "work_orders", "assets", "certificates", "inventory",
            "pending_confirmations",
        }

        def __init__(self, inner: "MiniSupabaseClient", org_id: str):
            self._inner = inner
            self._org_id = org_id

        def table(self, name: str):
            builder = self._inner.table(name)
            if name in self._ORG_TABLES:
                builder = builder.eq("organization_id", self._org_id)
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
        logger.warning("SUPABASE_URL or SUPABASE_SERVICE_KEY not set. Database features disabled.")
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

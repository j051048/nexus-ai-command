"""
P3 Enhancement: Database Connection Module

Provides a lightweight Supabase client wrapper using PostgREST.
Falls back gracefully when database is not configured.
"""

import hashlib
import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

url: str = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_URI", "")
key: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# Google Audit Fix:
# Due to dependency issues with 'storage3'/'pyiceberg' on Windows/C++ environment,
# we utilize a lightweight wrapper around 'postgrest' directly instead of the full 'supabase' client.
# This ensures Core RAG functions (Table Insert / RPC) work without bloat.

try:
    # Cache for scoped clients — P2 Fix: increased size + LRU eviction
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
            base_url = f"{url}/rest/v1"
            headers = {
                "apikey": key,
                "Authorization": f"Bearer {token or key}",
                "Content-Type": "application/json",
            }
            self.client = AsyncPostgrestClient(base_url, headers=headers)
            self._url = url  # Store for health checks
            self._key = key

        def table(self, name: str):
            return self.client.from_(name)

        def rpc(self, name: str, params: dict):
            return self.client.rpc(name, params)

        @property
        def is_configured(self) -> bool:
            """Check if client is properly configured"""
            return bool(self._url) and bool(self.client)

        def get_scoped_client(self, token: str):
            """Return a cached scoped client instance for RLS (LRU eviction)."""
            # P0 Security Fix: Use full SHA-256 hash of token as cache key
            cache_key = hashlib.sha256(token.encode()).hexdigest() if token else ""
            if cache_key in _scoped_client_cache:
                # P2 Fix: Move to end for LRU ordering
                _scoped_client_cache.move_to_end(cache_key)
                return _scoped_client_cache[cache_key]

            # Evict least recently used if cache full
            while len(_scoped_client_cache) >= _SCOPED_CLIENT_CACHE_MAX:
                _scoped_client_cache.popitem(last=False)

            client = MiniSupabaseClient(self._url, self._key, token)
            _scoped_client_cache[cache_key] = client
            return client

        def get_org_filtered_client(self, org_id: str):
            """Return an OrgFilteredClient that auto-injects org_id on every query."""
            return OrgFilteredClient(self, org_id)

    class OrgFilteredClient:
        """
        P0 Security Fix: Wrapper that auto-injects organization_id filter on every query.

        Used for API Key auth where no user JWT is available for RLS scoped clients.
        This ensures org isolation at the application level systematically — even if a
        route forgets to manually filter, the client handles it.
        """

        # Tables that use organization_id for multi-tenancy isolation
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
            """Return a query builder with automatic org_id filtering for known tables."""
            builder = self._inner.table(name)
            if name in self._ORG_TABLES:
                builder = builder.eq("organization_id", self._org_id)
            return builder

        def rpc(self, name: str, params: dict):
            """Pass through RPC calls, injecting p_org_id when not already present."""
            if "p_org_id" not in params and "organization_id" not in params:
                params = {**params, "p_org_id": self._org_id}
            return self._inner.rpc(name, params)

        @property
        def is_configured(self) -> bool:
            return self._inner.is_configured

        def get_scoped_client(self, token: str):
            """Delegate to inner client for JWT-based scoped access."""
            return self._inner.get_scoped_client(token)

        def get_org_filtered_client(self, org_id: str):
            """Return a new OrgFilteredClient (allow re-filtering)."""
            return OrgFilteredClient(self._inner, org_id)

    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_SERVICE_KEY not set. Database features disabled.")
        supabase = None
    else:
        supabase = MiniSupabaseClient(url, key)
        logger.info("Database client initialized successfully")

except ImportError as e:
    logger.error(f"Failed to import postgrest: {e}. Install with: pip install postgrest")
    supabase = None
except Exception as e:
    logger.error(f"Failed to initialize Supabase wrapper: {e}")
    supabase = None

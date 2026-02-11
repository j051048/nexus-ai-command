"""
P3 Enhancement: Database Connection Module

Provides a lightweight Supabase client wrapper using PostgREST.
Falls back gracefully when database is not configured.
"""

import os
import logging
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
    from postgrest import AsyncPostgrestClient

    # Cache for scoped clients (P2 Fix #16)
    _scoped_client_cache = {}
    _SCOPED_CLIENT_CACHE_MAX = 50

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
            """Return a cached scoped client instance for RLS."""
            # Use first 32 chars of token as cache key (sufficient for uniqueness)
            cache_key = token[:32] if token else ""
            if cache_key in _scoped_client_cache:
                return _scoped_client_cache[cache_key]

            # Evict oldest if cache full
            if len(_scoped_client_cache) >= _SCOPED_CLIENT_CACHE_MAX:
                oldest_key = next(iter(_scoped_client_cache))
                del _scoped_client_cache[oldest_key]

            client = MiniSupabaseClient(self._url, self._key, token)
            _scoped_client_cache[cache_key] = client
            return client

    if not url or not key:
        logger.warning(
            "SUPABASE_URL or SUPABASE_SERVICE_KEY not set. Database features disabled."
        )
        supabase = None
    else:
        supabase = MiniSupabaseClient(url, key)
        logger.info("Database client initialized successfully")

except ImportError as e:
    logger.error(
        f"Failed to import postgrest: {e}. Install with: pip install postgrest"
    )
    supabase = None
except Exception as e:
    logger.error(f"Failed to initialize Supabase wrapper: {e}")
    supabase = None

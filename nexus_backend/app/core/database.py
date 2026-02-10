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
                "Content-Type": "application/json"
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
            """
            Return a new client instance scoped to a specific user token (RLS).
            """
            return MiniSupabaseClient(self._url, self._key, token)

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


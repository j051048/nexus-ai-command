import os
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_URI", "")
key: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# Google Audit Fix:
# Due to dependency issues with 'storage3'/'pyiceberg' on Windows/C++ environment,
# we utilize a lightweight wrapper around 'postgrest' directly instead of the full 'supabase' client.
# This ensures Core RAG functions (Table Insert / RPC) work without bloat.

try:
    from postgrest import SyncPostgrestClient
    
    class MiniSupabaseClient:
        def __init__(self, url: str, key: str):
            # PostgREST expects base URL. Supabase URL usually ends with .co, needing /rest/v1 for PostgREST
            base_url = f"{url}/rest/v1"
            headers = {
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            self.client = SyncPostgrestClient(base_url, headers=headers)

        def table(self, name: str):
            return self.client.from_(name)

        def rpc(self, name: str, params: dict):
            return self.client.rpc(name, params)

    if not url or not key:
        print("Warning: SUPABASE_URL or SUPABASE_SERVICE_KEY not set.")
        supabase = None
    else:
        supabase = MiniSupabaseClient(url, key)
        
except ImportError as e:
    print(f"Failed to import postgrest: {e}")
    supabase = None
except Exception as e:
    print(f"Failed to initialize Supabase wrapper: {e}")
    supabase = None

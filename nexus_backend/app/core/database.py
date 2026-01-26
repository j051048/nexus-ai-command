import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL", "")
key: str = os.getenv("SUPABASE_SERVICE_KEY", "")

if not url or not key:
    print("Warning: SUPABASE_URL or SUPABASE_SERVICE_KEY not set. Supabase client will be None.")
    supabase = None
else:
    try:
        supabase: Client = create_client(url, key)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")
        supabase = None


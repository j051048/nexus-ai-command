import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import httpx

PROJECT_ROOT = Path(__file__).parent
BACKEND_ROOT = PROJECT_ROOT / "nexus_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(str(BACKEND_ROOT / ".env"), override=True)

async def test_retrieval():
    from app.core.config import settings
    base_url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
    }
    
    async with httpx.AsyncClient() as client:
        # 1. SCAN ALL DATA KEYS
        resp = await client.get(f"{base_url}/conversation_memories?select=key&limit=100", headers=headers)
        if resp.status_code != 200:
            print(f"ERROR: Fetch failed {resp.status_code}: {resp.text}")
            return
            
        keys = [r['key'] for r in resp.json()]
        print(f"FOUND {len(keys)} KEYS. SAMPLE: {keys[:10]}")
        
        # Search for 'conv'
        conv_keys = [k for k in keys if "conv" in k]
        print(f"CONV KEYS FOUND: {len(conv_keys)}")
        if conv_keys:
            print(f"FIRST CONV KEY: {conv_keys[0]}")

if __name__ == "__main__":
    asyncio.run(test_retrieval())

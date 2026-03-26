import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import httpx
from collections import Counter

PROJECT_ROOT = Path(__file__).parent
BACKEND_ROOT = PROJECT_ROOT / "nexus_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(str(BACKEND_ROOT / ".env"), override=True)

async def test_db_inventory():
    from app.core.config import settings
    base_url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
    }
    
    async with httpx.AsyncClient() as client:
        # Fetch up to 1000 items to check distributions
        resp = await client.get(f"{base_url}/conversation_memories?select=user_id,key&limit=2000", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            user_ids = [r['user_id'] for r in data]
            counts = Counter(user_ids)
            print("USER_ID COUNTS (Top 10):")
            for uid, c in counts.most_common(10):
                print(f" - {uid}: {c} records")
                # Show one sample key for this user
                for r in data:
                    if r['user_id'] == uid:
                        print(f"   Sample Key: {r['key']}")
                        break
        
if __name__ == "__main__":
    asyncio.run(test_db_inventory())

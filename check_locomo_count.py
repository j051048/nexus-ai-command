import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'nexus_backend'))

from app.core.database import supabase as db

async def check_count():
    try:
        # P3 Fix: Force HTTP/1.1 for this check too
        r = await db.table('conversation_memories').select('id', count='exact').filter('metadata->>source', 'eq', 'locomo').execute()
        print(f"COUNT: {r.count}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_count())

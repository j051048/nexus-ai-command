import asyncio
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'nexus_backend'))

from app.core.database import supabase as db

async def delete_locomo():
    try:
        # P3 Fix: Force delete locomo memories
        r = await db.table('conversation_memories').delete().filter('metadata->>source', 'eq', 'locomo').execute()
        print(f"DELETED: {len(r.data) if r.data else 0}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(delete_locomo())

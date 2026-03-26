import asyncio
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'nexus_backend'))

from app.core.database import supabase as db

async def check_metadata():
    try:
        r = await db.table('conversation_memories').select('metadata').filter('metadata->>source', 'eq', 'locomo').limit(1).execute()
        if r.data:
            print(f"METADATA: {r.data[0]['metadata']}")
        else:
            print("NO LOCOMO RECORDS YET")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_metadata())

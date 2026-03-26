import asyncio
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'nexus_backend'))

from app.core.database import supabase as db

async def check_latest():
    try:
        # Select newest 10 memories regardless of source
        r = await db.table('conversation_memories').select('created_at', 'metadata').order('created_at', desc=True).limit(10).execute()
        if r.data:
            for i, record in enumerate(r.data):
                print(f"[{i}] {record['created_at']} | {record['metadata'].get('source', 'unknown')} | {record['metadata'].get('doc_id', 'N/A')}")
        else:
            print("TABLE IS EMPTY")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_latest())

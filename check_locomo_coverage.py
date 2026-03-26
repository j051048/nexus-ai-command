import asyncio
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'nexus_backend'))

from app.core.database import supabase as db

async def check_coverage():
    try:
        # P3: Correct column is chat_session_id
        r = await db.table('conversation_memories').select('chat_session_id').filter('metadata->>source', 'eq', 'locomo').execute()
        sessions = set(record['chat_session_id'] for record in r.data)
        print(f"TOTAL UNIQUE SESSIONS IN DB: {len(sessions)}")
        print(f"TOTAL CHUNKS IN DB: {len(r.data)}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_coverage())

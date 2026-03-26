import asyncio
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'nexus_backend'))

from app.core.database import supabase as db

async def check_columns():
    try:
        # Select first row
        r = await db.table('conversation_memories').select('*').limit(1).execute()
        if r.data:
            print(f"COLUMNS: {list(r.data[0].keys())}")
        else:
            print("TABLE IS EMPTY")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_columns())

import asyncio
import sys
import os

# Add current dir to path to import app
sys.path.append(os.getcwd())

from app.core.database import supabase

async def find_user():
    try:
        res = await supabase.table('users').select('id').limit(1).execute()
        if res.data:
            print(f"REAL_USER_ID={res.data[0]['id']}")
        else:
            print("NO_USER_FOUND")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(find_user())

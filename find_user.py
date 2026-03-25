import asyncio
import os
import sys
from pathlib import Path

# Add project root and backend manually to sys.path
PROJECT_ROOT = Path(os.getcwd())
BACKEND_ROOT = PROJECT_ROOT / "nexus_backend"
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(BACKEND_ROOT))

async def get_valid_user():
    try:
        from nexus_backend.app.core.database import supabase
        # Try to get one user from auth.users via admin API or just a table that has user_id
        # Since we have service_role key, we might be able to query auth.users directly via RPC or similar
        # But safer to check a public table first
        response = await supabase.table('conversation_memories').select('user_id').limit(1).execute()
        if response.data:
            print(f"FOUND_USER_ID:{response.data[0]['user_id']}")
            return
            
        # If no memories, try to get from profiles if exists
        try:
            response = await supabase.table('profiles').select('id').limit(1).execute()
            if response.data:
                print(f"FOUND_USER_ID:{response.data[0]['id']}")
                return
        except:
            pass

        # Last resort: try auth.users (requires service_role)
        # However, supabase-py doesn't always expose auth.users easily without goTrue
        print("NO_USER_FOUND")
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(get_valid_user())

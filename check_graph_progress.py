import os
from pathlib import Path
from dotenv import load_dotenv
from postgrest import AsyncPostgrestClient

# Load env from absolute path
env_path = Path("c:/Users/Fei/Desktop/AI应用/nexus-ai-command/nexus_backend/.env")
load_dotenv(dotenv_path=env_path)

async def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    client = AsyncPostgrestClient(f"{url.rstrip('/')}/rest/v1", headers={"apikey": key, "Authorization": f"Bearer {key}"})
    
    # Target User
    uid = "83378b33-2e4e-4c6a-a25f-feced7c55115"
    
    # 1. Memories
    res_mems = await client.from_("conversation_memories").select("id", count="exact").eq("user_id", uid).execute()
    print(f"MEMORIES: {res_mems.count}")
        
    # 2. Entity Relations (The real graph)
    res_relations = await client.from_("entity_relations").select("id", count="exact").execute()
    # We count global since org_id might be null
    print(f"RELATIONS_GLOBAL: {res_relations.count}")

    # 3. Org Memories
    res_org = await client.from_("org_memories").select("id", count="exact").execute()
    print(f"ORG_MEMORIES_GLOBAL: {res_org.count}")
    
    # 4. Episodes
    res_episodes = await client.from_("conversation_episodes").select("id", count="exact").execute()
    print(f"EPISODES_GLOBAL: {res_episodes.count}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

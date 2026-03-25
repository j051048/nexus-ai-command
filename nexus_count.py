
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "nexus_backend"))

from nexus_backend.app.core.database import supabase

async def count_memories():
    try:
        # P1: Core logic: use ->> for text extraction from JSONB column in Supabase filters
        res = await supabase.table("conversation_memories") \
            .select("id", count="exact") \
            .eq("metadata->>source", "locomo") \
            .execute()
        
        print(f"LOCOMO_MEMORIES_COUNT={res.count}")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(count_memories())

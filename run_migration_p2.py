import asyncio
import sys
sys.path.insert(0, 'nexus_backend')
from app.core.database import supabase

async def run():
    sql = """CREATE TABLE IF NOT EXISTS state_snapshots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        thread_id TEXT NOT NULL,
        state JSONB NOT NULL,
        label TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )"""

    try:
        await supabase.rpc('exec_sql', {'query': sql}).execute()
        print('1. state_snapshots table: OK')
    except Exception as e:
        print(f'1. Error: {str(e)[:100]}')

    sql2 = "CREATE INDEX IF NOT EXISTS idx_snapshots_thread ON state_snapshots(thread_id, created_at DESC)"
    try:
        await supabase.rpc('exec_sql', {'query': sql2}).execute()
        print('2. Index: OK')
    except Exception as e:
        print(f'2. Error: {str(e)[:100]}')

asyncio.run(run())

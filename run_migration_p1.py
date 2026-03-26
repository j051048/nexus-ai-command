import asyncio
import sys
sys.path.insert(0, 'nexus_backend')
from app.core.database import supabase

async def run():
    sqls = [
        """CREATE TABLE IF NOT EXISTS agent_failures (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tool_name TEXT NOT NULL,
            error_pattern TEXT NOT NULL,
            context JSONB DEFAULT '{}',
            user_id UUID NOT NULL,
            org_id TEXT DEFAULT 'default',
            frequency INT DEFAULT 1,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS agent_successes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tool_name TEXT NOT NULL,
            solution TEXT NOT NULL,
            context JSONB DEFAULT '{}',
            org_id TEXT DEFAULT 'default',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS user_preferences (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            org_id TEXT DEFAULT 'default',
            preference_type TEXT NOT NULL,
            preference_data JSONB DEFAULT '{}',
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, preference_type)
        )""",

        "CREATE INDEX IF NOT EXISTS idx_failures_tool ON agent_failures(tool_name, org_id)",
        "CREATE INDEX IF NOT EXISTS idx_successes_tool ON agent_successes(tool_name, org_id)",
        "CREATE INDEX IF NOT EXISTS idx_preferences_user ON user_preferences(user_id, org_id)"
    ]

    for i, sql in enumerate(sqls, 1):
        try:
            await supabase.rpc('exec_sql', {'query': sql}).execute()
            print(f'{i}. OK')
        except Exception as e:
            print(f'{i}. {str(e)[:100]}')

asyncio.run(run())

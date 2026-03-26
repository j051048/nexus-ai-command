import asyncio
import sys
sys.path.insert(0, 'nexus_backend')
from app.core.database import supabase

async def run():
    sqls = [
        """CREATE TABLE IF NOT EXISTS agent_scheduled_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            cron_expression TEXT NOT NULL,
            prompt_template TEXT NOT NULL,
            user_id UUID NOT NULL,
            org_id TEXT DEFAULT 'default',
            enabled BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS agent_task_executions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id UUID REFERENCES agent_scheduled_tasks(id) ON DELETE CASCADE,
            executed_at TIMESTAMPTZ DEFAULT NOW(),
            status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
            result_summary TEXT,
            error_message TEXT
        )""",

        """CREATE TABLE IF NOT EXISTS agent_goals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            org_id TEXT DEFAULT 'default',
            goal_text TEXT NOT NULL,
            deadline TIMESTAMPTZ,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
            progress JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )""",

        "CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_enabled ON agent_scheduled_tasks(enabled) WHERE enabled = true",
        "CREATE INDEX IF NOT EXISTS idx_task_executions_task_id ON agent_task_executions(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_goals_user_status ON agent_goals(user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_goals_deadline ON agent_goals(deadline) WHERE status IN ('pending', 'in_progress')"
    ]

    for i, sql in enumerate(sqls, 1):
        try:
            await supabase.rpc('exec_sql', {'query': sql}).execute()
            print(f'{i}. OK')
        except Exception as e:
            print(f'{i}. {str(e)[:100]}')

asyncio.run(run())

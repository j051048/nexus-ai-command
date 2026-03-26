import asyncio
import sys
sys.path.insert(0, 'nexus_backend')
from app.core.database import supabase

async def run():
    sqls = [
        """CREATE TABLE IF NOT EXISTS tool_execution_audit (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tool_name TEXT NOT NULL,
            args JSONB NOT NULL,
            result JSONB,
            duration_ms INT,
            success BOOLEAN,
            error_message TEXT,
            user_id UUID NOT NULL,
            org_id TEXT DEFAULT 'default',
            trace_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS approval_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tool_name TEXT NOT NULL,
            args JSONB NOT NULL,
            user_id UUID NOT NULL,
            thread_id TEXT NOT NULL,
            org_id TEXT DEFAULT 'default',
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
            warning TEXT,
            approved_by UUID,
            approved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        "CREATE INDEX IF NOT EXISTS idx_audit_tool ON tool_execution_audit(tool_name, org_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_user ON tool_execution_audit(user_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_audit_trace ON tool_execution_audit(trace_id)",
        "CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_approval_user ON approval_requests(user_id, org_id)",

        """CREATE OR REPLACE FUNCTION get_tool_success_rate(since TIMESTAMPTZ)
        RETURNS FLOAT AS $$
        DECLARE
            total INT;
            successful INT;
        BEGIN
            SELECT COUNT(*) INTO total FROM tool_execution_audit WHERE created_at >= since;
            SELECT COUNT(*) INTO successful FROM tool_execution_audit WHERE created_at >= since AND success = true;
            IF total = 0 THEN RETURN 0.0; END IF;
            RETURN successful::FLOAT / total::FLOAT;
        END;
        $$ LANGUAGE plpgsql"""
    ]

    for i, sql in enumerate(sqls, 1):
        try:
            await supabase.rpc('exec_sql', {'query': sql}).execute()
            print(f'{i}. OK')
        except Exception as e:
            print(f'{i}. {str(e)[:100]}')

asyncio.run(run())

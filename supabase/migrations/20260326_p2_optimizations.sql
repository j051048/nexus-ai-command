-- P2 优化数据库迁移

-- 状态快照表
CREATE TABLE IF NOT EXISTS state_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id TEXT NOT NULL,
    state JSONB NOT NULL,
    label TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_thread ON state_snapshots(thread_id, created_at DESC);

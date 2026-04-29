-- Celery Dead Letter Queue (DLQ)
-- Records task failures for observability, debugging, and manual replay.

CREATE TABLE IF NOT EXISTS celery_dead_letters (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_name TEXT NOT NULL,
    task_id TEXT NOT NULL,
    args JSONB DEFAULT '[]'::jsonb,
    kwargs JSONB DEFAULT '{}'::jsonb,
    exception TEXT,
    traceback TEXT,
    retries INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 0,
    status TEXT DEFAULT 'dead' CHECK (status IN ('dead', 'replayed', 'resolved')),
    created_at TIMESTAMPTZ DEFAULT now(),
    replayed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_dlq_status ON celery_dead_letters(status);
CREATE INDEX IF NOT EXISTS idx_dlq_task_name ON celery_dead_letters(task_name);
CREATE INDEX IF NOT EXISTS idx_dlq_created ON celery_dead_letters(created_at DESC);

-- RLS: service_role has full access
ALTER TABLE celery_dead_letters ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full_access" ON celery_dead_letters
    FOR ALL TO service_role USING (true) WITH CHECK (true);

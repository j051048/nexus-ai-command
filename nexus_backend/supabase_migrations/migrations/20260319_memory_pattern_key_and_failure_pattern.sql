-- ============================================================
-- 1. conversation_memories: Pattern-Key 去重 + 量化晋升
-- ============================================================

ALTER TABLE conversation_memories
  ADD COLUMN IF NOT EXISTS pattern_key TEXT,
  ADD COLUMN IF NOT EXISTS recurrence_count INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_conversation_memories_pattern_key
  ON conversation_memories (user_id, pattern_key)
  WHERE pattern_key IS NOT NULL AND superseded_by IS NULL;

-- ============================================================
-- 2. agent_failure_logs: 错误模式分类
-- ============================================================

ALTER TABLE agent_failure_logs
  ADD COLUMN IF NOT EXISTS pattern_key TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_failure_logs_pattern_key
  ON agent_failure_logs (organization_id, pattern_key)
  WHERE pattern_key IS NOT NULL;

-- ============================================================
-- 定时任务分布式锁: 防止多实例重复执行
-- ============================================================

ALTER TABLE user_scheduled_tasks
  ADD COLUMN IF NOT EXISTS locked_by VARCHAR(64),
  ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ;

-- Index for stale lock cleanup
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_locked_at
  ON user_scheduled_tasks (locked_at)
  WHERE locked_by IS NOT NULL;

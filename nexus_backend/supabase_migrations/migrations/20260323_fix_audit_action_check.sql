-- 修复 memory_audit_log 的 action CHECK 约束
-- 新增 PROMOTE, MERGE, RESOLVE_CONFLICT 等记忆生命周期操作
-- 原始约束仅允许 ADD/UPDATE/DELETE，与 cleanup.py 中的 PROMOTE 操作冲突

ALTER TABLE IF EXISTS memory_audit_log
  DROP CONSTRAINT IF EXISTS memory_audit_log_action_check;

ALTER TABLE IF EXISTS memory_audit_log
  ADD CONSTRAINT memory_audit_log_action_check
  CHECK (action IN ('ADD', 'UPDATE', 'DELETE', 'PROMOTE', 'MERGE', 'RESOLVE_CONFLICT', 'DECAY'));

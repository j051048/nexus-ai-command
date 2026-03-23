-- S5: Memory Provenance Audit — add source tracking to audit log
-- Enables tracing where each memory came from and how it was extracted.

ALTER TABLE IF EXISTS memory_audit_log
  ADD COLUMN IF NOT EXISTS source TEXT,
  ADD COLUMN IF NOT EXISTS extraction_method TEXT;

COMMENT ON COLUMN memory_audit_log.source IS 'Provenance: where the memory originated (e.g. chat_session:uuid, tool:save_memory, consolidation:batch_id)';
COMMENT ON COLUMN memory_audit_log.extraction_method IS 'How the memory was extracted: regex, llm, user_explicit, consolidation, conflict_resolution';

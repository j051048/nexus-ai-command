-- ============================================================
-- Add versioning columns to conversation_memories
-- Code references superseded_by in 20+ places but the column
-- was never created, causing silent errors on every write.
-- ============================================================

ALTER TABLE conversation_memories
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS superseded_by UUID REFERENCES conversation_memories(id);

-- Index for cleanup job: find superseded records efficiently
CREATE INDEX IF NOT EXISTS idx_memories_superseded_by
    ON conversation_memories(superseded_by)
    WHERE superseded_by IS NOT NULL;

-- Composite index for version queries
CREATE INDEX IF NOT EXISTS idx_memories_user_key_version
    ON conversation_memories(user_id, key, version DESC);

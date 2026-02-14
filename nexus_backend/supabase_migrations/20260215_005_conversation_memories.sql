-- ============================================================
-- Item 13: Conversation Memories
-- AI conversation long-term memory storage
-- ============================================================

-- 会话记忆表
CREATE TABLE IF NOT EXISTS conversation_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id),
    category TEXT NOT NULL DEFAULT 'preference',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    importance FLOAT DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE conversation_memories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own memories"
    ON conversation_memories
    FOR ALL
    USING (user_id = auth.uid());

-- Indexes
CREATE INDEX IF NOT EXISTS idx_memories_user_category
    ON conversation_memories(user_id, category);

CREATE INDEX IF NOT EXISTS idx_memories_user_key
    ON conversation_memories(user_id, key);

CREATE INDEX IF NOT EXISTS idx_memories_importance
    ON conversation_memories(user_id, importance DESC);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_conversation_memories_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_conversation_memories_updated_at
    BEFORE UPDATE ON conversation_memories
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_memories_updated_at();

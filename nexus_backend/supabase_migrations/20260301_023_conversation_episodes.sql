-- P1-6: Conversation Episodes for Episodic Memory
-- Stores complete interaction trajectories for experience recall

CREATE TABLE IF NOT EXISTS conversation_episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    session_id TEXT NOT NULL DEFAULT 'default',

    -- Episode content
    user_intent TEXT NOT NULL,            -- One-line summary of what user wanted
    strategy TEXT NOT NULL DEFAULT '',     -- How the agent approached it (plan summary)
    tools_used TEXT[] DEFAULT '{}',        -- List of tool names invoked
    outcome TEXT NOT NULL DEFAULT '',      -- Final result summary
    confidence_score FLOAT DEFAULT 0.0,   -- Agent's confidence in the answer

    -- Metadata
    duration_ms INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    complexity TEXT DEFAULT 'moderate',    -- simple/moderate/complex/critical
    thinking_steps INT DEFAULT 0,

    -- Vector embedding for semantic search
    embedding vector(1536),

    created_at TIMESTAMPTZ DEFAULT now(),

    -- Index on user for fast retrieval
    CONSTRAINT fk_episode_user FOREIGN KEY (user_id) REFERENCES auth.users(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_episodes_user_id ON conversation_episodes(user_id);
CREATE INDEX IF NOT EXISTS idx_episodes_org_id ON conversation_episodes(organization_id);
CREATE INDEX IF NOT EXISTS idx_episodes_created_at ON conversation_episodes(created_at DESC);

-- Vector similarity search index (IVFFlat for reasonable dataset sizes)
CREATE INDEX IF NOT EXISTS idx_episodes_embedding ON conversation_episodes
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- RPC: Search episodes by embedding similarity
CREATE OR REPLACE FUNCTION search_episodes_by_embedding(
    query_embedding vector(1536),
    match_user_id UUID,
    match_limit INT DEFAULT 3,
    match_org_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    user_intent TEXT,
    strategy TEXT,
    tools_used TEXT[],
    outcome TEXT,
    confidence_score FLOAT,
    complexity TEXT,
    created_at TIMESTAMPTZ,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ce.id,
        ce.user_intent,
        ce.strategy,
        ce.tools_used,
        ce.outcome,
        ce.confidence_score,
        ce.complexity,
        ce.created_at,
        1 - (ce.embedding <=> query_embedding) AS similarity
    FROM conversation_episodes ce
    WHERE ce.user_id = match_user_id
      AND ce.embedding IS NOT NULL
      AND (match_org_id IS NULL OR ce.organization_id = match_org_id)
    ORDER BY ce.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$;

-- RLS Policies
ALTER TABLE conversation_episodes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own episodes"
    ON conversation_episodes FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own episodes"
    ON conversation_episodes FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role full access to episodes"
    ON conversation_episodes FOR ALL
    USING (auth.role() = 'service_role');

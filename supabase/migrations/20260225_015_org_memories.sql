-- Organization-level shared memory table
-- Stores knowledge, preferences, and rules shared across all users in an org

CREATE TABLE IF NOT EXISTS org_memories (
    id bigserial PRIMARY KEY,
    organization_id uuid NOT NULL,
    scope varchar(20) DEFAULT 'organization',
    category varchar(50) NOT NULL,        -- preference, knowledge, decision, case
    key varchar(500) NOT NULL,
    value text NOT NULL,
    contributed_by uuid,                   -- user who added this memory
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(organization_id, category, key)
);

-- RLS
ALTER TABLE org_memories ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_memories_tenant_isolation" ON org_memories
    USING (organization_id = current_setting('app.current_org_id', true)::uuid);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_org_memories_org ON org_memories(organization_id, category);
CREATE INDEX IF NOT EXISTS idx_org_memories_updated ON org_memories(organization_id, updated_at DESC);

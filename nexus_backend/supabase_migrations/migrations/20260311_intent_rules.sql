-- Intent classification keyword rules table
-- Allows admins to manage keyword→complexity mappings from DB instead of hardcoded Python dicts.
-- The router loads these at startup and caches them; hardcoded keywords serve as fallback.

CREATE TABLE IF NOT EXISTS intent_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword text NOT NULL,
    complexity text NOT NULL CHECK (complexity IN ('critical', 'complex', 'moderate')),
    category text,           -- optional grouping label (e.g. "approval", "finance", "hr")
    priority int DEFAULT 0,  -- higher priority rules evaluated first (unused for now, future-proof)
    is_active boolean DEFAULT true,
    tenant_id uuid REFERENCES organizations(id),  -- NULL = global rule
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Unique constraint: same keyword+complexity per tenant (or global)
CREATE UNIQUE INDEX IF NOT EXISTS idx_intent_rules_keyword_tenant
    ON intent_rules (keyword, complexity, COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'));

-- RLS
ALTER TABLE intent_rules ENABLE ROW LEVEL SECURITY;

-- Super admins can manage all rules; tenants can read global + own rules
CREATE POLICY "intent_rules_read" ON intent_rules
    FOR SELECT USING (
        tenant_id IS NULL
        OR tenant_id = (current_setting('app.current_tenant_id', true))::uuid
    );

CREATE POLICY "intent_rules_admin" ON intent_rules
    FOR ALL USING (
        EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('boss', 'founder'))
    );

COMMENT ON TABLE intent_rules IS 'Keyword-based intent classification rules for the AI router';

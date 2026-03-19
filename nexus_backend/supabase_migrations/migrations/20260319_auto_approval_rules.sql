-- Auto Approval Rules: organization-level rules for automatic approval
-- Used by approval_chain_service to skip human review when conditions match.

CREATE TABLE IF NOT EXISTS auto_approval_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name text NOT NULL,
    approval_type text NOT NULL,          -- expense, leave, purchase, etc.
    condition_field text NOT NULL,         -- field to check: amount, days, etc.
    condition_op text NOT NULL DEFAULT 'lte', -- lte, gte, eq, lt, gt
    condition_value numeric NOT NULL,      -- threshold value
    is_active boolean NOT NULL DEFAULT true,
    created_by uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_auto_approval_rules_org
    ON auto_approval_rules(organization_id, approval_type)
    WHERE is_active = true;

ALTER TABLE auto_approval_rules ENABLE ROW LEVEL SECURITY;

CREATE POLICY "auto_approval_rules_org_read"
    ON auto_approval_rules FOR SELECT
    USING (organization_id IN (
        SELECT organization_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "auto_approval_rules_org_write"
    ON auto_approval_rules FOR ALL
    USING (organization_id IN (
        SELECT organization_id FROM users WHERE id = auth.uid()
        AND role IN ('boss', 'founder')
    ));

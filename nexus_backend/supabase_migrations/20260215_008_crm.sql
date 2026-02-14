-- CRM Tables: Customers, Contacts, Activities
-- All tables enforce organization-level isolation via RLS

-- ─── Customers ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    company TEXT,
    industry TEXT,
    stage TEXT DEFAULT 'lead' CHECK (stage IN ('lead', 'prospect', 'opportunity', 'customer', 'churned')),
    source TEXT,
    estimated_value DECIMAL(12,2),
    assigned_to UUID REFERENCES auth.users(id),
    tags TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customers_org ON customers(organization_id);
CREATE INDEX IF NOT EXISTS idx_customers_stage ON customers(stage);
CREATE INDEX IF NOT EXISTS idx_customers_assigned ON customers(assigned_to);
CREATE INDEX IF NOT EXISTS idx_customers_updated ON customers(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers USING gin(name gin_trgm_ops);

-- ─── Customer Contacts ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS customer_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    title TEXT,
    phone TEXT,
    email TEXT,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_contacts_customer ON customer_contacts(customer_id);

-- ─── Customer Activities ───────────────────────────────────

CREATE TABLE IF NOT EXISTS customer_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    activity_type TEXT NOT NULL CHECK (activity_type IN ('call', 'email', 'meeting', 'note', 'deal_update')),
    content TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_activities_customer ON customer_activities(customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_activities_created ON customer_activities(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_customer_activities_type ON customer_activities(activity_type);

-- ─── Row Level Security ────────────────────────────────────

ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_activities ENABLE ROW LEVEL SECURITY;

-- Customers: organization isolation
CREATE POLICY customers_org_isolation ON customers
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- Contacts: accessible if the parent customer is accessible
CREATE POLICY customer_contacts_org_isolation ON customer_contacts
    FOR ALL
    USING (
        customer_id IN (
            SELECT c.id FROM customers c
            JOIN users u ON u.organization_id = c.organization_id
            WHERE u.id = auth.uid()
        )
    );

-- Activities: accessible if the parent customer is accessible
CREATE POLICY customer_activities_org_isolation ON customer_activities
    FOR ALL
    USING (
        customer_id IN (
            SELECT c.id FROM customers c
            JOIN users u ON u.organization_id = c.organization_id
            WHERE u.id = auth.uid()
        )
    );

-- ─── Updated_at triggers ───────────────────────────────────

CREATE OR REPLACE FUNCTION update_customers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_customers_updated_at();

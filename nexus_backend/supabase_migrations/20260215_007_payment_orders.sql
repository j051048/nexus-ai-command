-- Payment Orders table for domestic payment integration
-- Supports bank transfer, WeChat Pay, and Alipay

CREATE TABLE IF NOT EXISTS payment_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    order_no TEXT NOT NULL UNIQUE,
    plan_id TEXT,
    payment_method TEXT NOT NULL CHECK (payment_method IN ('bank_transfer', 'wechat_pay', 'alipay')),
    amount DECIMAL(10,2) NOT NULL,
    currency TEXT DEFAULT 'CNY',
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'cancelled', 'refunded', 'failed')),
    paid_at TIMESTAMPTZ,
    invoice_status TEXT DEFAULT 'none' CHECK (invoice_status IN ('none', 'requested', 'issued')),
    invoice_info JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_payment_orders_org ON payment_orders(organization_id);
CREATE INDEX IF NOT EXISTS idx_payment_orders_status ON payment_orders(status);
CREATE INDEX IF NOT EXISTS idx_payment_orders_created ON payment_orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payment_orders_order_no ON payment_orders(order_no);

-- Row Level Security
ALTER TABLE payment_orders ENABLE ROW LEVEL SECURITY;

-- Policy: Organizations can only see their own orders
CREATE POLICY payment_orders_org_isolation ON payment_orders
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_payment_orders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_payment_orders_updated_at
    BEFORE UPDATE ON payment_orders
    FOR EACH ROW
    EXECUTE FUNCTION update_payment_orders_updated_at();

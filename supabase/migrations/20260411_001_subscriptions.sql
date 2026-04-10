-- 20260411_001: Subscriptions + tenant_subscriptions tables
-- Referenced by: billing_service.py, payment_gateway.py

-- 1. subscriptions table (billing_service.py uses .upsert with org_id as conflict key)
CREATE TABLE IF NOT EXISTS subscriptions (
  org_id TEXT NOT NULL,
  plan TEXT NOT NULL DEFAULT 'free',
  status TEXT NOT NULL DEFAULT 'active',
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  current_period_end TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_subscriptions PRIMARY KEY (org_id)
);

-- 2. tenant_subscriptions table (payment_gateway.py uses upsert on tenant_id,stripe_subscription_id)
CREATE TABLE IF NOT EXISTS tenant_subscriptions (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  stripe_subscription_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  current_period_start TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ,
  cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_tenant_subscriptions PRIMARY KEY (id),
  CONSTRAINT uq_tenant_sub_tenant_stripe UNIQUE (tenant_id, stripe_subscription_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan ON subscriptions (plan);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions (status);
CREATE INDEX IF NOT EXISTS idx_tenant_sub_tenant ON tenant_subscriptions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_sub_status ON tenant_subscriptions (status);

-- RLS
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_subscriptions ENABLE ROW LEVEL SECURITY;

-- RLS policies: org members can read/write their own org's subscriptions
CREATE POLICY subscriptions_org_isolation ON subscriptions
  FOR ALL USING (org_id = get_user_org_id());

CREATE POLICY tenant_subscriptions_org_isolation ON tenant_subscriptions
  FOR ALL USING (tenant_id = get_user_org_id());

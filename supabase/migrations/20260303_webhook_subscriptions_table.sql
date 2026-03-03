-- S-1 Fix: Webhook subscriptions DB persistence
-- Provides durable storage so subscriptions survive restarts

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id TEXT PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    url TEXT NOT NULL,
    events JSONB NOT NULL DEFAULT '[]',
    secret_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT DEFAULT '',
    failure_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_subs_org_active
    ON webhook_subscriptions(org_id) WHERE is_active = TRUE;

-- RLS
ALTER TABLE webhook_subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "webhook_subs_org_isolation" ON webhook_subscriptions
    FOR ALL USING (org_id = current_setting('app.current_org_id', true)::uuid);

-- Webhook delivery log (audit trail)
CREATE TABLE IF NOT EXISTS webhook_delivery_log (
    id TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL REFERENCES webhook_subscriptions(id),
    event TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    response_code INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_delivery_sub
    ON webhook_delivery_log(subscription_id);

ALTER TABLE webhook_delivery_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "webhook_delivery_org_isolation" ON webhook_delivery_log
    FOR ALL USING (
        subscription_id IN (
            SELECT id FROM webhook_subscriptions
            WHERE org_id = current_setting('app.current_org_id', true)::uuid
        )
    );

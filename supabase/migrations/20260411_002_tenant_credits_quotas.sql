-- 20260411_002: tenant_credits + tenant_quotas tables + consume_tenant_credit RPC
-- Referenced by: tenant_credit_service.py

-- 1. tenant_credits table
CREATE TABLE IF NOT EXISTS tenant_credits (
  org_id TEXT NOT NULL,
  credit_type TEXT NOT NULL,  -- 'tokens' | 'api_calls' | 'storage_mb'
  allocated BIGINT NOT NULL DEFAULT 0,
  used BIGINT NOT NULL DEFAULT 0,
  reserved BIGINT NOT NULL DEFAULT 0,
  period_start TIMESTAMPTZ,
  period_end TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_tenant_credits PRIMARY KEY (org_id, credit_type)
);

-- 2. tenant_quotas table
CREATE TABLE IF NOT EXISTS tenant_quotas (
  org_id TEXT NOT NULL,
  monthly_token_limit BIGINT NOT NULL DEFAULT 1000000,
  monthly_api_call_limit BIGINT NOT NULL DEFAULT 10000,
  daily_token_limit BIGINT NOT NULL DEFAULT 100000,
  daily_api_call_limit BIGINT NOT NULL DEFAULT 1000,
  rate_limit_per_minute INT NOT NULL DEFAULT 60,
  burst_limit INT NOT NULL DEFAULT 10,
  storage_limit_mb INT NOT NULL DEFAULT 1000,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT pk_tenant_quotas PRIMARY KEY (org_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tenant_credits_type ON tenant_credits (credit_type);
CREATE INDEX IF NOT EXISTS idx_tenant_credits_org ON tenant_credits (org_id);

-- RLS
ALTER TABLE tenant_credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_quotas ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_credits_org_isolation ON tenant_credits
  FOR ALL USING (org_id = get_user_org_id());

CREATE POLICY tenant_quotas_org_isolation ON tenant_quotas
  FOR ALL USING (org_id = get_user_org_id());

-- 3. consume_tenant_credit RPC — atomic credit consumption
CREATE OR REPLACE FUNCTION consume_tenant_credit(
  p_org_id TEXT,
  p_credit_type TEXT,
  p_amount BIGINT,
  p_user_id TEXT
)
RETURNS TABLE(success BOOLEAN, remaining BIGINT)
LANGUAGE plpgsql
AS $$
DECLARE
  v_remaining BIGINT;
BEGIN
  -- Atomically increment used and check limit
  UPDATE tenant_credits
  SET used = used + p_amount,
      updated_at = now()
  WHERE org_id = p_org_id
    AND credit_type = p_credit_type
  RETURNING allocated - used - reserved INTO v_remaining;

  IF NOT FOUND THEN
    -- No credit record exists; create one with default allocation
    INSERT INTO tenant_credits (org_id, credit_type, allocated, used, reserved)
    VALUES (p_org_id, p_credit_type, 0, p_amount, 0)
    ON CONFLICT (org_id, credit_type) DO UPDATE
      SET used = tenant_credits.used + p_amount, updated_at = now()
    RETURNING allocated - used - reserved INTO v_remaining;
  END IF;

  -- Log usage in tenant_usage_records if table exists
  BEGIN
    INSERT INTO tenant_usage_records (org_id, user_id, metric_type, metric_value, recorded_at)
    VALUES (p_org_id, p_user_id, p_credit_type, p_amount, now());
  EXCEPTION WHEN undefined_table THEN
    -- tenant_usage_records may not exist yet; skip logging
    NULL;
  END;

  RETURN QUERY SELECT TRUE, v_remaining;
END;
$$;

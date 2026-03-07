-- Migration: Add Token Usage Tables-- P1 Fix #13: Token Usage Persistence Tables
-- Stores token usage data durably so it survives process restarts.

-- 1. Append-only log of every LLM API call
CREATE TABLE IF NOT EXISTS token_usage_log (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES auth.users(id),
    usage_date date NOT NULL DEFAULT CURRENT_DATE,
    model text NOT NULL DEFAULT 'unknown',
    input_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    total_tokens integer NOT NULL DEFAULT 0,
    cost_usd numeric(10, 6) NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Index for querying by user and date
CREATE INDEX IF NOT EXISTS idx_token_usage_log_user_date 
    ON token_usage_log(user_id, usage_date);

-- 2. Daily aggregate per user (upserted on each request)
CREATE TABLE IF NOT EXISTS token_usage_daily (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES auth.users(id),
    usage_date date NOT NULL DEFAULT CURRENT_DATE,
    total_tokens bigint NOT NULL DEFAULT 0,
    total_cost_usd numeric(12, 6) NOT NULL DEFAULT 0,
    request_count integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(user_id, usage_date)
);

CREATE INDEX IF NOT EXISTS idx_token_usage_daily_user_date 
    ON token_usage_daily(user_id, usage_date);

-- 3. RPC function: Atomic upsert for daily aggregate
-- Uses ON CONFLICT to safely handle concurrent writes
CREATE OR REPLACE FUNCTION upsert_daily_token_usage(
    p_user_id uuid,
    p_date date,
    p_tokens integer,
    p_cost numeric
) RETURNS void AS $$
BEGIN
    INSERT INTO token_usage_daily (user_id, usage_date, total_tokens, total_cost_usd, request_count, updated_at)
    VALUES (p_user_id, p_date, p_tokens, p_cost, 1, now())
    ON CONFLICT (user_id, usage_date)
    DO UPDATE SET
        total_tokens = token_usage_daily.total_tokens + EXCLUDED.total_tokens,
        total_cost_usd = token_usage_daily.total_cost_usd + EXCLUDED.total_cost_usd,
        request_count = token_usage_daily.request_count + 1,
        updated_at = now();
END;
$$ LANGUAGE plpgsql;

-- 4. RLS Policies
ALTER TABLE token_usage_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_usage_daily ENABLE ROW LEVEL SECURITY;

-- Users can read their own usage
CREATE POLICY "Users can view own usage log" ON token_usage_log
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can view own daily usage" ON token_usage_daily
    FOR SELECT USING (auth.uid() = user_id);

-- Service role can insert/update (backend uses service key)
CREATE POLICY "Service can insert usage log" ON token_usage_log
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Service can manage daily usage" ON token_usage_daily
    FOR ALL USING (true) WITH CHECK (true);
-- AI Quality Daily Metrics - Aggregated daily stats for quality dashboard
CREATE TABLE IF NOT EXISTS ai_quality_daily (
    id bigserial PRIMARY KEY,
    tenant_id uuid,
    metric_date date NOT NULL,
    total_traces int DEFAULT 0,
    completed_traces int DEFAULT 0,
    failed_traces int DEFAULT 0,
    timeout_traces int DEFAULT 0,
    total_tokens bigint DEFAULT 0,
    total_cost_usd numeric(10,4) DEFAULT 0,
    avg_duration_ms int DEFAULT 0,
    hallucination_count int DEFAULT 0,
    tool_calls_total int DEFAULT 0,
    tool_calls_success int DEFAULT 0,
    tool_calls_failed int DEFAULT 0,
    positive_feedback int DEFAULT 0,
    negative_feedback int DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    UNIQUE(tenant_id, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_ai_quality_daily_tenant ON ai_quality_daily(tenant_id, metric_date);

-- AI Feedback table - stores user feedback on AI responses
CREATE TABLE IF NOT EXISTS ai_feedback (
    id bigserial PRIMARY KEY,
    tenant_id uuid,
    user_id uuid NOT NULL,
    session_id varchar(200),
    message_index int,
    rating varchar(10) NOT NULL,  -- 'positive' or 'negative'
    comment text,
    ai_response_snippet text,
    query_snippet text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_feedback_tenant ON ai_feedback(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_feedback_user ON ai_feedback(user_id, created_at);

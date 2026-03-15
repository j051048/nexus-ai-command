-- Tenant usage metering tables
CREATE TABLE IF NOT EXISTS tenant_usage_records (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    record_type TEXT NOT NULL CHECK (record_type IN ('llm', 'tool', 'rag', 'storage')),
    model_name TEXT,
    tool_name TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd NUMERIC(10,6) DEFAULT 0,
    execution_time_ms INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tenant_usage_tenant_type ON tenant_usage_records(tenant_id, record_type, created_at);
CREATE INDEX idx_tenant_usage_created ON tenant_usage_records(created_at);

-- Monthly aggregation view
CREATE OR REPLACE VIEW tenant_usage_monthly AS
SELECT
    tenant_id,
    record_type,
    DATE_TRUNC('month', created_at) AS month,
    COUNT(*) AS total_calls,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    SUM(cost_usd) AS total_cost_usd,
    AVG(execution_time_ms) AS avg_execution_time_ms
FROM tenant_usage_records
GROUP BY tenant_id, record_type, DATE_TRUNC('month', created_at);

-- RLS
ALTER TABLE tenant_usage_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_usage_isolation ON tenant_usage_records
    USING (tenant_id = (SELECT organization_id FROM users WHERE id = auth.uid()));

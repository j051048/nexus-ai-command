-- Multi-dimensional Usage Statistics Table

CREATE TABLE IF NOT EXISTS llm_usage_stats (
  id bigserial PRIMARY KEY,
  tenant_id uuid,
  stat_date date NOT NULL,
  model_code varchar(100) DEFAULT '_all',
  scene_code varchar(100) DEFAULT '_all',
  agent_code varchar(100) DEFAULT '_all',
  user_id uuid,
  department_id uuid,
  total_calls int DEFAULT 0,
  total_input_tokens bigint DEFAULT 0,
  total_output_tokens bigint DEFAULT 0,
  total_cost decimal(12,4) DEFAULT 0,
  success_count int DEFAULT 0,
  fail_count int DEFAULT 0,
  avg_exec_time_ms int DEFAULT 0,
  create_time timestamptz DEFAULT now(),
  UNIQUE(tenant_id, stat_date, model_code, scene_code, agent_code, user_id)
);

CREATE INDEX idx_llm_usage_stats_query ON llm_usage_stats(tenant_id, stat_date DESC, model_code);
CREATE INDEX idx_llm_usage_stats_user ON llm_usage_stats(tenant_id, user_id, stat_date DESC);

-- Quota configuration table
CREATE TABLE IF NOT EXISTS llm_quota_config (
  id bigserial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id),
  quota_type varchar(30) NOT NULL, -- model/user/department/scene
  target_id varchar(200), -- model_code or user_id or department_id or scene_code
  daily_token_limit bigint,
  daily_cost_limit decimal(10,2),
  monthly_token_limit bigint,
  monthly_cost_limit decimal(10,2),
  daily_request_limit int,
  overage_action varchar(20) DEFAULT 'warn', -- warn/block
  alert_threshold_pct int DEFAULT 80,
  is_active boolean DEFAULT true,
  create_time timestamptz DEFAULT now(),
  update_time timestamptz DEFAULT now()
);

ALTER TABLE llm_quota_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY "llm_quota_config_tenant_isolation" ON llm_quota_config
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

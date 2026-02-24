-- Model Call Log Table (partitioned by month for performance)

CREATE TABLE IF NOT EXISTS llm_call_log (
  id bigserial PRIMARY KEY,
  tenant_id uuid,
  request_id varchar(100),
  user_id uuid,
  scene_code varchar(100),
  agent_code varchar(100),
  model_code varchar(100),
  model_name varchar(200),
  input_tokens int DEFAULT 0,
  output_tokens int DEFAULT 0,
  total_tokens int DEFAULT 0,
  call_cost decimal(12,6) DEFAULT 0,
  exec_time_ms int DEFAULT 0,
  status varchar(20) DEFAULT 'success', -- success/failed/timeout/fallback
  fallback_model_code varchar(100),
  finish_reason varchar(30), -- stop/tool_calls/length/error
  error_message text,
  create_time timestamptz DEFAULT now()
);

CREATE INDEX idx_llm_call_log_tenant_time ON llm_call_log(tenant_id, create_time DESC);
CREATE INDEX idx_llm_call_log_request ON llm_call_log(request_id);
CREATE INDEX idx_llm_call_log_user ON llm_call_log(tenant_id, user_id, create_time DESC);
CREATE INDEX idx_llm_call_log_model ON llm_call_log(tenant_id, model_code, create_time DESC);

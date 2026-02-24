-- LLM Model Configuration Tables for Multi-Model Adaptation Gateway

-- Model configuration table
CREATE TABLE IF NOT EXISTS llm_model_config (
  id bigserial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id),
  model_code varchar(100) NOT NULL,
  model_name varchar(200) NOT NULL,
  provider_type varchar(50) NOT NULL, -- openai_compatible/wenxin/tongyi/hunyuan/doubao/deepseek/yi_lingyi/anthropic
  adapter_code varchar(100) NOT NULL,
  api_base_url text NOT NULL,
  api_key_encrypted text NOT NULL,
  secret_key_encrypted text, -- For providers that need a second key (e.g., Baidu)
  model_id varchar(200) NOT NULL, -- Provider's model identifier
  timeout_ms int DEFAULT 30000,
  max_retries int DEFAULT 3,
  max_tokens int,
  context_window int,
  supports_tools boolean DEFAULT true,
  supports_streaming boolean DEFAULT true,
  supports_vision boolean DEFAULT false,
  model_type varchar(20) DEFAULT 'chat', -- chat/embedding/multimodal
  input_price_per_1m decimal(10,4),
  output_price_per_1m decimal(10,4),
  default_temperature decimal(3,2) DEFAULT 0.70,
  default_top_p decimal(3,2) DEFAULT 0.90,
  status varchar(20) DEFAULT 'enabled', -- enabled/disabled/testing
  is_default boolean DEFAULT false,
  sort_order int DEFAULT 0,
  create_time timestamptz DEFAULT now(),
  update_time timestamptz DEFAULT now(),
  is_deleted boolean DEFAULT false,
  UNIQUE(tenant_id, model_code)
);

-- RLS
ALTER TABLE llm_model_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY "llm_model_config_tenant_isolation" ON llm_model_config
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

-- Indexes
CREATE INDEX idx_llm_model_config_tenant ON llm_model_config(tenant_id);
CREATE INDEX idx_llm_model_config_status ON llm_model_config(tenant_id, status, is_deleted);
CREATE INDEX idx_llm_model_config_type ON llm_model_config(tenant_id, model_type, status);

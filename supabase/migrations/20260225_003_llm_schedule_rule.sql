-- Model Scheduling Rules Table

CREATE TABLE IF NOT EXISTS llm_schedule_rule (
  id bigserial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id),
  rule_name varchar(200) NOT NULL,
  scene_code varchar(100) NOT NULL,
  agent_code varchar(100), -- NULL means global rule for this scene
  primary_model_id bigint REFERENCES llm_model_config(id),
  backup_model_id bigint REFERENCES llm_model_config(id),
  load_balance_strategy varchar(30) DEFAULT 'priority', -- priority/round_robin/least_calls
  priority int DEFAULT 0,
  is_active boolean DEFAULT true,
  create_time timestamptz DEFAULT now(),
  update_time timestamptz DEFAULT now(),
  UNIQUE(tenant_id, scene_code, agent_code)
);

ALTER TABLE llm_schedule_rule ENABLE ROW LEVEL SECURITY;
CREATE POLICY "llm_schedule_rule_tenant_isolation" ON llm_schedule_rule
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

CREATE INDEX idx_llm_schedule_rule_lookup ON llm_schedule_rule(tenant_id, scene_code, agent_code, is_active);

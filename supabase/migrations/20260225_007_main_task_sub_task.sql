-- VMD Task Management Tables

CREATE TABLE IF NOT EXISTS vmd_main_task (
  id bigserial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id),
  task_code varchar(50) NOT NULL,
  user_id uuid NOT NULL,
  title varchar(500) NOT NULL,
  description text,
  original_input text,
  scene_code varchar(100),
  wbs_structure jsonb,
  status varchar(30) DEFAULT 'pending', -- pending/decomposing/executing/reviewing/completed/failed/cancelled
  priority varchar(20) DEFAULT 'normal', -- low/normal/high/urgent
  deadline timestamptz,
  total_sub_tasks int DEFAULT 0,
  completed_sub_tasks int DEFAULT 0,
  final_output text,
  total_tokens_used bigint DEFAULT 0,
  total_cost decimal(12,4) DEFAULT 0,
  create_time timestamptz DEFAULT now(),
  update_time timestamptz DEFAULT now(),
  is_deleted boolean DEFAULT false,
  UNIQUE(tenant_id, task_code)
);

ALTER TABLE vmd_main_task ENABLE ROW LEVEL SECURITY;
CREATE POLICY "vmd_main_task_tenant_isolation" ON vmd_main_task
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

CREATE INDEX idx_vmd_main_task_user ON vmd_main_task(tenant_id, user_id, create_time DESC);
CREATE INDEX idx_vmd_main_task_status ON vmd_main_task(tenant_id, status, create_time DESC);

CREATE TABLE IF NOT EXISTS vmd_sub_task (
  id bigserial PRIMARY KEY,
  main_task_id bigint NOT NULL REFERENCES vmd_main_task(id),
  tenant_id uuid,
  sub_task_code varchar(50),
  agent_code varchar(100) NOT NULL,
  title varchar(500) NOT NULL,
  description text,
  dependencies jsonb DEFAULT '[]'::jsonb,
  input_context text,
  output_content text,
  status varchar(30) DEFAULT 'pending', -- pending/waiting_dependency/executing/completed/failed/reviewing/rejected
  exec_start_time timestamptz,
  exec_end_time timestamptz,
  model_code varchar(100),
  token_usage jsonb,
  review_status varchar(20), -- NULL/approved/rejected
  review_comment text,
  reviewer_id uuid,
  sort_order int DEFAULT 0,
  create_time timestamptz DEFAULT now(),
  update_time timestamptz DEFAULT now()
);

CREATE INDEX idx_vmd_sub_task_main ON vmd_sub_task(main_task_id, sort_order);
CREATE INDEX idx_vmd_sub_task_status ON vmd_sub_task(tenant_id, status);
CREATE INDEX idx_vmd_sub_task_agent ON vmd_sub_task(agent_code, status);

-- Task audit record
CREATE TABLE IF NOT EXISTS vmd_task_audit_record (
  id bigserial PRIMARY KEY,
  tenant_id uuid,
  task_id bigint NOT NULL,
  task_type varchar(10) NOT NULL, -- main/sub
  action varchar(20) NOT NULL, -- approve/reject/resubmit/cancel
  reviewer_id uuid,
  comment text,
  create_time timestamptz DEFAULT now()
);

CREATE INDEX idx_vmd_task_audit_task ON vmd_task_audit_record(task_id, task_type);

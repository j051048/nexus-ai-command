-- Bid / Tender Project Management Table

-- ============================================================
-- 1. bid_project — 招投标项目管理
-- ============================================================
CREATE TABLE IF NOT EXISTS bid_project (
  id bigserial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id),
  project_code varchar(100),
  project_name varchar(500),
  client_name varchar(200),
  bid_deadline timestamptz,
  estimated_value numeric(15,2),
  status varchar(30) DEFAULT 'preparation', -- preparation/in_progress/submitted/won/lost/cancelled
  bid_type varchar(50), -- public/invited/competitive_negotiation
  requirements_summary text,
  our_advantages text,
  competitor_info text,
  assigned_team jsonb,
  documents jsonb,
  compliance_status varchar(20) DEFAULT 'unchecked', -- unchecked/passed/has_issues
  created_by uuid,
  create_time timestamptz DEFAULT now(),
  update_time timestamptz DEFAULT now(),
  UNIQUE(tenant_id, project_code)
);

-- RLS
ALTER TABLE bid_project ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bid_project_tenant_isolation" ON bid_project
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

-- Indexes
CREATE INDEX idx_bid_project_tenant ON bid_project(tenant_id);
CREATE INDEX idx_bid_project_status ON bid_project(tenant_id, status);
CREATE INDEX idx_bid_project_deadline ON bid_project(tenant_id, bid_deadline);
CREATE INDEX idx_bid_project_client ON bid_project(tenant_id, client_name);
CREATE INDEX idx_bid_project_create_time ON bid_project(tenant_id, create_time DESC);

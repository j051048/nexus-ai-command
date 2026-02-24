-- Business Clue / Lead Management Tables

-- ============================================================
-- 1. business_clue — 商机线索
-- ============================================================
CREATE TABLE IF NOT EXISTS business_clue (
  id bigserial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id),
  clue_code varchar(100),
  source varchar(50) NOT NULL, -- manual/crawler/referral/exhibition/bidding_info
  source_url text,
  title varchar(500),
  content text,
  industry varchar(100),
  region varchar(100),
  estimated_value numeric(15,2),
  priority varchar(20) DEFAULT 'medium', -- low/medium/high/urgent
  status varchar(30) DEFAULT 'new', -- new/contacted/qualified/converted/lost
  assigned_to uuid,
  customer_id uuid,
  tags text[],
  created_by uuid,
  create_time timestamptz DEFAULT now(),
  update_time timestamptz DEFAULT now(),
  UNIQUE(tenant_id, clue_code)
);

-- RLS
ALTER TABLE business_clue ENABLE ROW LEVEL SECURITY;
CREATE POLICY "business_clue_tenant_isolation" ON business_clue
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

-- Indexes
CREATE INDEX idx_business_clue_tenant ON business_clue(tenant_id);
CREATE INDEX idx_business_clue_status ON business_clue(tenant_id, status);
CREATE INDEX idx_business_clue_source ON business_clue(tenant_id, source);
CREATE INDEX idx_business_clue_assigned ON business_clue(assigned_to);
CREATE INDEX idx_business_clue_priority ON business_clue(tenant_id, priority);
CREATE INDEX idx_business_clue_create_time ON business_clue(tenant_id, create_time DESC);

-- ============================================================
-- 2. clue_follow_up — 线索跟进记录
-- ============================================================
CREATE TABLE IF NOT EXISTS clue_follow_up (
  id bigserial PRIMARY KEY,
  clue_id bigint NOT NULL REFERENCES business_clue(id),
  user_id uuid,
  action varchar(50),
  content text,
  next_action varchar(200),
  next_action_date date,
  created_at timestamptz DEFAULT now()
);

-- RLS
ALTER TABLE clue_follow_up ENABLE ROW LEVEL SECURITY;
CREATE POLICY "clue_follow_up_tenant_isolation" ON clue_follow_up
  USING (
    EXISTS (
      SELECT 1 FROM business_clue bc
      WHERE bc.id = clue_follow_up.clue_id
        AND bc.tenant_id = current_setting('app.current_org_id', true)::uuid
    )
  );

-- Indexes
CREATE INDEX idx_clue_follow_up_clue ON clue_follow_up(clue_id, created_at DESC);
CREATE INDEX idx_clue_follow_up_user ON clue_follow_up(user_id);
CREATE INDEX idx_clue_follow_up_next_action ON clue_follow_up(next_action_date);

-- Schema Extensions: Add columns used by service layer but missing from base migrations.
-- This ensures compatibility between Python services and the database schema.

-- ============================================================
-- 1. business_clue — extra columns for ClueService
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'company') THEN
    ALTER TABLE business_clue ADD COLUMN company varchar(200);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'contact_name') THEN
    ALTER TABLE business_clue ADD COLUMN contact_name varchar(100);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'contact_phone') THEN
    ALTER TABLE business_clue ADD COLUMN contact_phone varchar(50);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'contact_email') THEN
    ALTER TABLE business_clue ADD COLUMN contact_email varchar(200);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'level') THEN
    ALTER TABLE business_clue ADD COLUMN level varchar(10) DEFAULT 'C';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'product_interest') THEN
    ALTER TABLE business_clue ADD COLUMN product_interest text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'description') THEN
    ALTER TABLE business_clue ADD COLUMN description text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'metadata') THEN
    ALTER TABLE business_clue ADD COLUMN metadata jsonb DEFAULT '{}'::jsonb;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_clue' AND column_name = 'updated_by') THEN
    ALTER TABLE business_clue ADD COLUMN updated_by uuid;
  END IF;
END $$;

-- ============================================================
-- 2. bid_project — extra columns for BidService
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'title') THEN
    ALTER TABLE bid_project ADD COLUMN title varchar(500);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'tender_number') THEN
    ALTER TABLE bid_project ADD COLUMN tender_number varchar(200);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'buyer_name') THEN
    ALTER TABLE bid_project ADD COLUMN buyer_name varchar(200);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'buyer_contact') THEN
    ALTER TABLE bid_project ADD COLUMN buyer_contact varchar(200);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'deadline') THEN
    ALTER TABLE bid_project ADD COLUMN deadline timestamptz;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'bid_opening_date') THEN
    ALTER TABLE bid_project ADD COLUMN bid_opening_date timestamptz;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'our_products') THEN
    ALTER TABLE bid_project ADD COLUMN our_products text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'competitors') THEN
    ALTER TABLE bid_project ADD COLUMN competitors text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'win_probability') THEN
    ALTER TABLE bid_project ADD COLUMN win_probability int DEFAULT 0;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'notes') THEN
    ALTER TABLE bid_project ADD COLUMN notes text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'metadata') THEN
    ALTER TABLE bid_project ADD COLUMN metadata jsonb DEFAULT '{}'::jsonb;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'assigned_to') THEN
    ALTER TABLE bid_project ADD COLUMN assigned_to uuid;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bid_project' AND column_name = 'updated_by') THEN
    ALTER TABLE bid_project ADD COLUMN updated_by uuid;
  END IF;
END $$;

-- ============================================================
-- 3. compliance_check_log — extra columns for ComplianceService
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'task_id') THEN
    ALTER TABLE compliance_check_log ADD COLUMN task_id varchar(100);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'agent_code') THEN
    ALTER TABLE compliance_check_log ADD COLUMN agent_code varchar(100);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'check_status') THEN
    ALTER TABLE compliance_check_log ADD COLUMN check_status varchar(30);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'errors') THEN
    ALTER TABLE compliance_check_log ADD COLUMN errors int DEFAULT 0;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'warnings') THEN
    ALTER TABLE compliance_check_log ADD COLUMN warnings int DEFAULT 0;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'issues_detail') THEN
    ALTER TABLE compliance_check_log ADD COLUMN issues_detail jsonb DEFAULT '[]'::jsonb;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'content_snippet') THEN
    ALTER TABLE compliance_check_log ADD COLUMN content_snippet text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'categories') THEN
    ALTER TABLE compliance_check_log ADD COLUMN categories text[];
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'use_llm') THEN
    ALTER TABLE compliance_check_log ADD COLUMN use_llm boolean DEFAULT false;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'status') THEN
    ALTER TABLE compliance_check_log ADD COLUMN status varchar(30);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'high_issues') THEN
    ALTER TABLE compliance_check_log ADD COLUMN high_issues int DEFAULT 0;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'medium_issues') THEN
    ALTER TABLE compliance_check_log ADD COLUMN medium_issues int DEFAULT 0;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'low_issues') THEN
    ALTER TABLE compliance_check_log ADD COLUMN low_issues int DEFAULT 0;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_check_log' AND column_name = 'checked_at') THEN
    ALTER TABLE compliance_check_log ADD COLUMN checked_at timestamptz DEFAULT now();
  END IF;
END $$;

-- ============================================================
-- 4. compliance_rule — extra columns for router CRUD
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_rule' AND column_name = 'created_by') THEN
    ALTER TABLE compliance_rule ADD COLUMN created_by uuid;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'compliance_rule' AND column_name = 'updated_by') THEN
    ALTER TABLE compliance_rule ADD COLUMN updated_by uuid;
  END IF;
END $$;

-- ============================================================
-- 5. vmd_main_task — extra columns used by routers
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_main_task' AND column_name = 'created_by') THEN
    ALTER TABLE vmd_main_task ADD COLUMN created_by uuid;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_main_task' AND column_name = 'updated_by') THEN
    ALTER TABLE vmd_main_task ADD COLUMN updated_by uuid;
  END IF;
END $$;

-- ============================================================
-- 6. vmd_sub_task — extra columns used by routers
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_sub_task' AND column_name = 'updated_by') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN updated_by uuid;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_sub_task' AND column_name = 'retry_count') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN retry_count int DEFAULT 0;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_sub_task' AND column_name = 'error_message') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN error_message text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_sub_task' AND column_name = 'reviewed_by') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN reviewed_by uuid;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_sub_task' AND column_name = 'reviewed_at') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN reviewed_at timestamptz;
  END IF;
END $$;

-- ============================================================
-- 7. vmd_agent_config — extra columns used by routers
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_agent_config' AND column_name = 'updated_by') THEN
    ALTER TABLE vmd_agent_config ADD COLUMN updated_by uuid;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_agent_config' AND column_name = 'max_retries') THEN
    ALTER TABLE vmd_agent_config ADD COLUMN max_retries int DEFAULT 3;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_agent_config' AND column_name = 'timeout_ms') THEN
    ALTER TABLE vmd_agent_config ADD COLUMN timeout_ms int DEFAULT 60000;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_agent_config' AND column_name = 'model_code') THEN
    ALTER TABLE vmd_agent_config ADD COLUMN model_code varchar(100);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'vmd_agent_config' AND column_name = 'status') THEN
    ALTER TABLE vmd_agent_config ADD COLUMN status varchar(20) DEFAULT 'active';
  END IF;
END $$;

-- ============================================================
-- 8. vmd_reports — table for report persistence
-- ============================================================
CREATE TABLE IF NOT EXISTS vmd_reports (
  id bigserial PRIMARY KEY,
  tenant_id uuid,
  report_type varchar(30) NOT NULL,
  report_date varchar(20),
  report_data jsonb DEFAULT '{}'::jsonb,
  report_content text,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vmd_reports_tenant ON vmd_reports(tenant_id, report_type, report_date);

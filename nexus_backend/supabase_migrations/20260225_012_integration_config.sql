-- External System Integration Configuration & Sync Log Tables

-- ============================================================
-- 1. integration_config — 外部集成配置
-- ============================================================
CREATE TABLE IF NOT EXISTS integration_config (
  id bigserial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id),
  integration_type varchar(50) NOT NULL, -- crawler/erp/crm_external/email/wechat
  integration_name varchar(200),
  config jsonb,
  credentials jsonb,
  status varchar(20) DEFAULT 'inactive', -- inactive/active/error
  last_sync_at timestamptz,
  sync_interval_minutes int DEFAULT 60,
  created_by uuid,
  create_time timestamptz DEFAULT now(),
  UNIQUE(tenant_id, integration_type, integration_name)
);

-- RLS
ALTER TABLE integration_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY "integration_config_tenant_isolation" ON integration_config
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

-- Indexes
CREATE INDEX idx_integration_config_tenant ON integration_config(tenant_id);
CREATE INDEX idx_integration_config_type ON integration_config(tenant_id, integration_type);
CREATE INDEX idx_integration_config_status ON integration_config(tenant_id, status);

-- ============================================================
-- 2. integration_sync_log — 同步日志
-- ============================================================
CREATE TABLE IF NOT EXISTS integration_sync_log (
  id bigserial PRIMARY KEY,
  integration_id bigint NOT NULL REFERENCES integration_config(id),
  sync_type varchar(50),
  status varchar(20), -- running/success/partial/failed
  records_processed int DEFAULT 0,
  records_failed int DEFAULT 0,
  error_message text,
  started_at timestamptz DEFAULT now(),
  completed_at timestamptz
);

-- RLS
ALTER TABLE integration_sync_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "integration_sync_log_tenant_isolation" ON integration_sync_log
  USING (
    EXISTS (
      SELECT 1 FROM integration_config ic
      WHERE ic.id = integration_sync_log.integration_id
        AND ic.tenant_id = current_setting('app.current_org_id', true)::uuid
    )
  );

-- Indexes
CREATE INDEX idx_integration_sync_log_integration ON integration_sync_log(integration_id, started_at DESC);
CREATE INDEX idx_integration_sync_log_status ON integration_sync_log(status);

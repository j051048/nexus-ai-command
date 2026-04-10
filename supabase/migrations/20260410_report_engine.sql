-- Report Engine: saved reports and scheduled reports
-- saved_reports: stores generated report results (SQL + data + chart config)
-- report_schedules: scheduled report generation + push delivery

CREATE TABLE IF NOT EXISTS saved_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  nl_query TEXT NOT NULL,               -- original natural language query
  generated_sql TEXT NOT NULL,           -- AI-generated SQL
  result_data JSONB DEFAULT '[]',        -- query result rows
  chart_config JSONB DEFAULT '{}',       -- { type, x_key, y_keys, colors, ... }
  summary TEXT,                          -- AI-generated summary/insights
  is_public BOOLEAN DEFAULT false,       -- shared within org
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS report_schedules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  nl_query TEXT NOT NULL,                -- natural language query to regenerate
  schedule_type TEXT NOT NULL DEFAULT 'daily' CHECK (schedule_type IN ('daily', 'weekly', 'monthly')),
  hour INT NOT NULL DEFAULT 9 CHECK (hour >= 0 AND hour < 24),
  day_of_week INT DEFAULT 1 CHECK (day_of_week >= 0 AND day_of_week <= 6), -- 0=Mon
  day_of_month INT DEFAULT 1 CHECK (day_of_month >= 1 AND day_of_month <= 28),
  recipients JSONB DEFAULT '[]',         -- [{ type: "email", value: "..." }, { type: "user_id", value: "..." }]
  output_format TEXT DEFAULT 'table' CHECK (output_format IN ('table', 'chart', 'both')),
  is_active BOOLEAN DEFAULT true,
  last_executed_at TIMESTAMPTZ,
  next_execution_at TIMESTAMPTZ,
  last_report_id UUID REFERENCES saved_reports(id) ON DELETE SET NULL,
  failure_count INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_saved_reports_org ON saved_reports(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_saved_reports_user ON saved_reports(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_schedules_org ON report_schedules(organization_id, is_active);
CREATE INDEX IF NOT EXISTS idx_report_schedules_next ON report_schedules(next_execution_at) WHERE is_active = true;

-- RLS
ALTER TABLE saved_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_schedules ENABLE ROW LEVEL SECURITY;

CREATE POLICY "saved_reports_org_isolation" ON saved_reports
  FOR ALL USING (organization_id = (SELECT organization_id FROM users WHERE id = auth.uid()));

CREATE POLICY "saved_reports_select_public" ON saved_reports
  FOR SELECT USING (is_public = true AND organization_id = (SELECT organization_id FROM users WHERE id = auth.uid()));

CREATE POLICY "report_schedules_org_isolation" ON report_schedules
  FOR ALL USING (organization_id = (SELECT organization_id FROM users WHERE id = auth.uid()));

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_saved_reports_updated_at() RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_report_schedules_updated_at() RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_saved_reports_updated BEFORE UPDATE ON saved_reports
  FOR EACH ROW EXECUTE FUNCTION update_saved_reports_updated_at();

CREATE TRIGGER trg_report_schedules_updated BEFORE UPDATE ON report_schedules
  FOR EACH ROW EXECUTE FUNCTION update_report_schedules_updated_at();

COMMENT ON TABLE saved_reports IS 'AI-generated report results with SQL, data, and chart config';
COMMENT ON TABLE report_schedules IS 'Scheduled report generation with push delivery to recipients';

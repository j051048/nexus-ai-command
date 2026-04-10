-- 20260411_004: Add lead scoring columns to sales_leads
-- Referenced by: lead_scoring_service.py

-- Add scoring columns if not exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'sales_leads' AND column_name = 'score'
  ) THEN
    ALTER TABLE sales_leads ADD COLUMN score REAL DEFAULT 0;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'sales_leads' AND column_name = 'win_probability'
  ) THEN
    ALTER TABLE sales_leads ADD COLUMN win_probability REAL DEFAULT 0;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'sales_leads' AND column_name = 'ai_suggestion'
  ) THEN
    ALTER TABLE sales_leads ADD COLUMN ai_suggestion TEXT;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'sales_leads' AND column_name = 'last_scored_at'
  ) THEN
    ALTER TABLE sales_leads ADD COLUMN last_scored_at TIMESTAMPTZ;
  END IF;
END $$;

-- Index for score-based queries
CREATE INDEX IF NOT EXISTS idx_sales_leads_score ON sales_leads (score DESC);
CREATE INDEX IF NOT EXISTS idx_sales_leads_win_prob ON sales_leads (win_probability DESC);

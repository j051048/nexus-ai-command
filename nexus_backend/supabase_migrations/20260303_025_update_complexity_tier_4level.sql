-- Update complexity_tier values from 2-level (low/high) to 4-level naming
-- New tiers: economy | balanced | power | flagship

-- Update column comment
COMMENT ON COLUMN llm_schedule_rule.complexity_tier IS
  'Query complexity tier: economy | balanced | power | flagship | NULL (wildcard)';

-- Migrate any existing old-format values
UPDATE llm_schedule_rule SET complexity_tier = 'economy' WHERE complexity_tier = 'low';
UPDATE llm_schedule_rule SET complexity_tier = 'power' WHERE complexity_tier = 'high';

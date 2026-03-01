-- P2-9: Add complexity_tier to llm_schedule_rule for complexity-aware model routing
-- This enables the Gateway to select different models based on query complexity
-- (e.g., simple queries → cheap model, complex queries → powerful model)

-- 1. Add complexity_tier column (NULL = wildcard, applies to all complexity levels)
ALTER TABLE llm_schedule_rule
  ADD COLUMN IF NOT EXISTS complexity_tier varchar(20) DEFAULT NULL;

COMMENT ON COLUMN llm_schedule_rule.complexity_tier IS
  'Query complexity tier: low (simple/moderate) | high (complex/critical) | NULL (wildcard)';

-- 2. Drop old unique constraint and create new one that includes complexity_tier
-- Use COALESCE to handle NULL in unique index (NULL != NULL in SQL)
ALTER TABLE llm_schedule_rule
  DROP CONSTRAINT IF EXISTS llm_schedule_rule_tenant_id_scene_code_agent_code_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_schedule_rule_full
  ON llm_schedule_rule(tenant_id, scene_code, COALESCE(agent_code, ''), COALESCE(complexity_tier, '__null__'));

-- 3. Rebuild lookup index to include complexity_tier
DROP INDEX IF EXISTS idx_llm_schedule_rule_lookup;
CREATE INDEX idx_llm_schedule_rule_lookup
  ON llm_schedule_rule(tenant_id, scene_code, agent_code, complexity_tier, is_active);

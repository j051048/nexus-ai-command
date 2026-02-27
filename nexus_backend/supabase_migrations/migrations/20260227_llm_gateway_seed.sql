-- ============================================================================
-- Model Gateway Seed Data: Models + Schedule Rules for apiyi.com proxy
-- All models route through https://api.apiyi.com/v1 (OpenAI-compatible)
-- ============================================================================

-- Add model_code text columns to schedule_rule for direct gateway resolution
ALTER TABLE llm_schedule_rule ADD COLUMN IF NOT EXISTS primary_model_code varchar(100);
ALTER TABLE llm_schedule_rule ADD COLUMN IF NOT EXISTS backup_model_code varchar(100);

-- Note: The actual model configs and schedule rules are inserted via
-- application-level seed script (requires API key encryption).
-- See the LLM Model Management page (/llm/models) for GUI-based management.
--
-- Pre-seeded models (16 total):
--   HIGH:    claude-sonnet-4-6, gpt-4o, gemini-2.5-pro, deepseek-v3
--   MEDIUM:  gemini-3-flash-preview (default), gpt-4o-mini, qwen-plus-latest, claude-haiku-4-5
--   LOW:     gemini-2.5-flash, qwen-turbo-latest, deepseek-chat
--   REASON:  deepseek-r1, o3-mini
--   EMBED:   text-embedding-3-small, text-embedding-3-large, bge-m3
--
-- Schedule rules (9 total):
--   Global default: gemini-3-flash-preview (backup: gpt-4o-mini)
--   director_agent: claude-sonnet-4-6 (backup: deepseek-v3)
--   sales_agent:    gpt-4o (backup: deepseek-v3)
--   content_agent:  gemini-3-flash-preview (backup: qwen-plus-latest)
--   clue_agent:     gemini-3-flash-preview (backup: claude-haiku-4-5)
--   operation_agent: qwen-plus-latest (backup: gemini-3-flash-preview)
--   embedding:      text-embedding-3-small (backup: bge-m3)
--   deep_analysis:  deepseek-r1 (backup: o3-mini)
--   summary:        gemini-2.5-flash (backup: deepseek-chat)

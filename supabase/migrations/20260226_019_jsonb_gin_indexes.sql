-- ============================================================================
-- Migration 019: Add GIN indexes for high-frequency JSONB columns
-- Date: 2026-02-26
-- Purpose: Prevent slow nested JSONB queries as data grows.
--          Uses jsonb_path_ops for containment-only queries (@>),
--          and default jsonb_ops where key-existence (?) is also needed.
-- ============================================================================

-- 1. documents.extracted_data — AI-extracted metadata, queried by field values
CREATE INDEX IF NOT EXISTS idx_documents_extracted_data_gin
  ON documents USING GIN (extracted_data jsonb_path_ops);

-- 2. documents.metadata — upload metadata, occasional filtering
CREATE INDEX IF NOT EXISTS idx_documents_metadata_gin
  ON documents USING GIN (metadata jsonb_path_ops);

-- 3. chat_messages.metadata — conversation context, tool calls, etc.
CREATE INDEX IF NOT EXISTS idx_chat_messages_metadata_gin
  ON chat_messages USING GIN (metadata jsonb_path_ops);

-- 4. workflow_definitions.definition — workflow node/edge JSON, searched during execution
CREATE INDEX IF NOT EXISTS idx_workflow_definitions_definition_gin
  ON workflow_definitions USING GIN (definition jsonb_path_ops);

-- 5. form_schemas.schema — dynamic form JSON schema, queried for field matching
CREATE INDEX IF NOT EXISTS idx_form_schemas_schema_gin
  ON form_schemas USING GIN (schema jsonb_path_ops);

-- 6. vmd_agent_configs.config — agent configuration JSON
CREATE INDEX IF NOT EXISTS idx_vmd_agent_configs_config_gin
  ON vmd_agent_configs USING GIN (config jsonb_path_ops);

-- 7. llm_call_logs.request_payload / response_payload — debugging & audit queries
CREATE INDEX IF NOT EXISTS idx_llm_call_logs_request_gin
  ON llm_call_logs USING GIN (request_payload jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_llm_call_logs_response_gin
  ON llm_call_logs USING GIN (response_payload jsonb_path_ops);

-- 8. notification_items.data — notification payload filtering
CREATE INDEX IF NOT EXISTS idx_notification_items_data_gin
  ON notification_items USING GIN (data jsonb_path_ops);

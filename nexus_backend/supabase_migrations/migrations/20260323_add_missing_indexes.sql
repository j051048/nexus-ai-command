-- Add missing indexes for high-frequency query patterns
-- These columns are frequently used in WHERE/JOIN clauses without indexes

-- conversation_memories: queried by user_id + tenant_id on every chat request
CREATE INDEX IF NOT EXISTS idx_conversation_memories_user_tenant
  ON conversation_memories(user_id, tenant_id);

-- conversation_memories: time-based cleanup and retrieval
CREATE INDEX IF NOT EXISTS idx_conversation_memories_created_at
  ON conversation_memories(created_at DESC);

-- sales_leads: list queries filter by tenant + stage
CREATE INDEX IF NOT EXISTS idx_sales_leads_tenant_stage
  ON sales_leads(tenant_id, stage);

-- documents: list queries filter by tenant + status
CREATE INDEX IF NOT EXISTS idx_documents_tenant_status
  ON documents(tenant_id, status);

-- document_embeddings: re-embed queries filter by embedding_model
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_model
  ON document_embeddings(embedding_model);

-- approval_requests: list queries filter by organization + status
CREATE INDEX IF NOT EXISTS idx_approval_requests_org_status
  ON approval_requests(organization_id, status);

-- agent_quality_scores: trend queries filter by created_at
CREATE INDEX IF NOT EXISTS idx_agent_quality_created
  ON agent_quality_scores(created_at);

-- user_scheduled_tasks: cron queries filter by is_active + next_run_at
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_active_next
  ON user_scheduled_tasks(is_active, next_run_at)
  WHERE is_active = true;

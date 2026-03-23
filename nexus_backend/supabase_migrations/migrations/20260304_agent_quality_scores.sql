-- Agent 质量评分表 - Critic 评审结果持久化
-- 用于积累评分数据，为后续路由权重优化打基础
CREATE TABLE IF NOT EXISTS agent_quality_scores (
  id bigserial PRIMARY KEY,
  tenant_id uuid,
  user_id uuid,
  session_id varchar(200),
  trace_id varchar(100),

  -- 查询上下文
  scene_code varchar(100),
  agent_code varchar(100),
  complexity varchar(20),
  intent_summary text,

  -- Critic 评分
  completeness decimal(3,2) NOT NULL,
  relevance decimal(3,2) NOT NULL,
  accuracy decimal(3,2) NOT NULL,
  quality_score decimal(3,2) GENERATED ALWAYS AS (
    LEAST(completeness, relevance, accuracy)
  ) STORED,
  passed boolean NOT NULL DEFAULT true,
  improvement_suggestion text,

  -- 执行元数据
  model_code varchar(100),
  iteration int DEFAULT 0,
  response_length int,
  tool_call_count int DEFAULT 0,

  create_time timestamptz DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_aq_scores_tenant_time
  ON agent_quality_scores(tenant_id, create_time DESC);
CREATE INDEX IF NOT EXISTS idx_aq_scores_trace
  ON agent_quality_scores(trace_id);
CREATE INDEX IF NOT EXISTS idx_aq_scores_quality
  ON agent_quality_scores(tenant_id, passed, quality_score);
CREATE INDEX IF NOT EXISTS idx_aq_scores_scene
  ON agent_quality_scores(tenant_id, scene_code, agent_code, create_time DESC);

-- RLS
ALTER TABLE agent_quality_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "aq_scores_tenant_isolation" ON agent_quality_scores
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

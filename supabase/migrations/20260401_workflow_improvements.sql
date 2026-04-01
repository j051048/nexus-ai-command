-- Phase 1: 支持执行确认节点和驳回重提
-- 迁移时间: 2026-04-01

-- 1. approval_requests 表增加字段
ALTER TABLE approval_requests
ADD COLUMN IF NOT EXISTS reject_to_step INT,
ADD COLUMN IF NOT EXISTS resubmit_count INT DEFAULT 0;

-- 2. 创建并行审批决策表
CREATE TABLE IF NOT EXISTS parallel_approval_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID REFERENCES approval_requests(id) ON DELETE CASCADE,
  step_index INT NOT NULL,
  approver_id UUID NOT NULL,
  decision VARCHAR(20) NOT NULL,
  comment TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_parallel_decisions_request
ON parallel_approval_decisions(request_id, step_index);

-- 3. 创建执行记录表
CREATE TABLE IF NOT EXISTS workflow_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID REFERENCES approval_requests(id) ON DELETE CASCADE,
  executor_id UUID NOT NULL,
  action VARCHAR(100) NOT NULL,
  evidence_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_executions_request
ON workflow_executions(request_id);

-- Soul Document: 租户级 AI 灵魂/人格定义
-- 每个租户一份，由 boss/founder 配置，定义 AI 助手的核心人格

CREATE TABLE IF NOT EXISTS soul_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL UNIQUE,  -- 每个租户仅一份
  -- 结构化字段
  ai_name TEXT DEFAULT '小助手' CHECK (char_length(ai_name) <= 50),
  identity TEXT CHECK (char_length(identity) <= 500),           -- 身份定位
  personality TEXT CHECK (char_length(personality) <= 500),      -- 性格特征
  values TEXT CHECK (char_length(values) <= 1000),              -- 价值观/原则
  language_style TEXT CHECK (char_length(language_style) <= 500), -- 语言风格
  taboos TEXT CHECK (char_length(taboos) <= 1000),              -- 禁忌/红线
  custom_instructions TEXT CHECK (char_length(custom_instructions) <= 3000), -- 自由文本
  -- 控制
  is_active BOOLEAN DEFAULT true,
  version INT DEFAULT 1,
  -- 审计
  created_by UUID NOT NULL,
  updated_by UUID,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_soul_documents_tenant ON soul_documents(tenant_id);

-- RLS
ALTER TABLE soul_documents ENABLE ROW LEVEL SECURITY;

-- 同租户内所有成员可读
CREATE POLICY "soul_doc_tenant_read" ON soul_documents
  FOR SELECT USING (
    tenant_id IN (
      SELECT organization_id FROM organization_members WHERE user_id = auth.uid()
    )
  );

-- 仅 boss/founder 可写（INSERT/UPDATE/DELETE）
CREATE POLICY "soul_doc_boss_write" ON soul_documents
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM organization_members om
      JOIN users u ON u.id = om.user_id
      WHERE om.user_id = auth.uid()
        AND om.organization_id = soul_documents.tenant_id
        AND u.role IN ('boss', 'founder')
    )
  ) WITH CHECK (
    EXISTS (
      SELECT 1 FROM organization_members om
      JOIN users u ON u.id = om.user_id
      WHERE om.user_id = auth.uid()
        AND om.organization_id = soul_documents.tenant_id
        AND u.role IN ('boss', 'founder')
    )
  );

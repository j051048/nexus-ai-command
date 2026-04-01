-- Knowledge Library Management (分库管理)

CREATE TABLE IF NOT EXISTS knowledge_library (
  id bigserial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id),
  library_code varchar(100) NOT NULL,
  library_name varchar(200) NOT NULL,
  description text,
  access_level varchar(30) DEFAULT 'organization', -- organization/department/private
  department_id uuid,
  owner_id uuid,
  doc_count int DEFAULT 0,
  is_active boolean DEFAULT true,
  create_time timestamptz DEFAULT now(),
  update_time timestamptz DEFAULT now(),
  UNIQUE(tenant_id, library_code)
);

ALTER TABLE knowledge_library ENABLE ROW LEVEL SECURITY;
CREATE POLICY "knowledge_library_tenant_isolation" ON knowledge_library
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

-- Add library_id to existing documents table
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'library_id') THEN
    ALTER TABLE documents ADD COLUMN library_id bigint REFERENCES knowledge_library(id);
    CREATE INDEX idx_documents_library ON documents(library_id);
  END IF;
END $$;

-- Add model_code to document_embeddings for tracking which embedding model was used
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'document_embeddings' AND column_name = 'embedding_model_code') THEN
    ALTER TABLE document_embeddings ADD COLUMN embedding_model_code varchar(100) DEFAULT 'text-embedding-3-small';
  END IF;
END $$;

-- Seed default knowledge libraries
INSERT INTO knowledge_library (tenant_id, library_code, library_name, description, access_level)
VALUES
  (NULL, 'product_lib', '产品知识库', '产品手册、技术参数、应用方案等产品相关文档', 'organization'),
  (NULL, 'regulation_lib', '法规标准库', '行业法规、国家标准、检测标准等合规文档', 'organization'),
  (NULL, 'case_lib', '案例库', '客户案例、应用案例、解决方案等', 'organization'),
  (NULL, 'tender_lib', '招投标库', '招标文件、投标文件、标书模板等', 'department'),
  (NULL, 'training_lib', '培训知识库', '培训材料、销售话术、FAQ等', 'organization'),
  (NULL, 'competitor_lib', '竞品情报库', '竞品资料、市场分析、行业报告等', 'department')
ON CONFLICT DO NOTHING;

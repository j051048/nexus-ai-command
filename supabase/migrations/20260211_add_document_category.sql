-- =============================================================================
-- H6: 知识库分类管理
-- 添加 category 字段到 documents 表，支持分类筛选
-- =============================================================================

-- Step 1: 添加 category 字段
ALTER TABLE public.documents 
  ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'other' 
  CHECK (category IN ('regulation', 'manual', 'contract', 'training', 'other'));

-- Step 2: 为已有数据设置默认分类（基于 doc_type）
UPDATE public.documents 
SET category = CASE 
  WHEN doc_type = 'contract' THEN 'contract'
  WHEN doc_type = 'bid' THEN 'other'
  WHEN doc_type = 'product' THEN 'manual'
  ELSE 'other'
END
WHERE category IS NULL OR category = 'other';

-- Step 3: 创建索引提升查询性能
CREATE INDEX IF NOT EXISTS idx_documents_category ON public.documents(category);

-- Step 4: 注释说明
COMMENT ON COLUMN public.documents.category IS '文档分类：regulation(规章制度)、manual(产品手册)、contract(合同模板)、training(培训资料)、other(其他)';

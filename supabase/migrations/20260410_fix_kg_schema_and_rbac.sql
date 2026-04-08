-- Migration: Fix KG Schema and RBAC
-- Date: 2026-04-10

-- 1. 修复 knowledge_graph_triples 表结构
ALTER TABLE knowledge_graph_triples 
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id),
ADD COLUMN IF NOT EXISTS visibility TEXT DEFAULT 'team' CHECK (visibility IN ('private', 'team', 'organization')),
ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 1.0;

-- 如果 created_by 存在，回填数据
UPDATE knowledge_graph_triples SET user_id = created_by WHERE user_id IS NULL AND created_by IS NOT NULL;

-- 2. 修复 conversation_memories 表结构
ALTER TABLE conversation_memories
ADD COLUMN IF NOT EXISTS visibility TEXT DEFAULT 'private' CHECK (visibility IN ('private', 'team', 'organization')),
ADD COLUMN IF NOT EXISTS semantic_tags TEXT[] DEFAULT '{}';

-- 3. 创建索引
CREATE INDEX IF NOT EXISTS idx_conversation_memories_semantic_tags ON conversation_memories USING GIN (semantic_tags);
CREATE INDEX IF NOT EXISTS idx_kg_organization_visibility ON knowledge_graph_triples(organization_id, visibility);

-- 4. 启用 RLS 并添加策略
ALTER TABLE knowledge_graph_triples ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_memories ENABLE ROW LEVEL SECURITY;

-- 删除可能存在的冲突策略
DROP POLICY IF EXISTS "Users can view and manage org graph triples" ON knowledge_graph_triples;
DROP POLICY IF EXISTS "Users can view team and org memories" ON conversation_memories;

-- 创建策略
CREATE POLICY "Users can view and manage org graph triples"
    ON knowledge_graph_triples
    FOR ALL
    USING (
        user_id = auth.uid() 
        OR visibility IN ('team', 'organization')
    );

CREATE POLICY "Users can view team and org memories"
    ON conversation_memories
    FOR SELECT
    USING (
        user_id = auth.uid() 
        OR visibility IN ('team', 'organization')
    );

# Graph Memory 试点设计文档

> 在 CRM / 组织架构场景引入轻量级知识图谱，增强 Agent 对实体关系的理解和推理能力。

## 1. 动机

当前 `conversation_memories` 和 `vector_service` 均为"扁平"存储：每条记忆或文档片段独立存在，缺乏实体间的关联信息。这导致以下场景表现不佳：

- "张总的下属有哪些人？" —— 需要遍历所有记忆才能拼凑组织架构
- "跟华为相关的所有销售线索和联系人" —— 跨表跨记忆难以聚合
- "李经理上次提到的那个供应商叫什么" —— 需要实体消歧和关系回溯

知识图谱可以将实体和关系显式建模，使 Agent 能通过图遍历快速获取结构化上下文。

## 2. 数据模型

### 2.1 核心表结构（PostgreSQL 原生方案）

```sql
-- 实体表：人物、组织、产品、项目等
CREATE TABLE IF NOT EXISTS graph_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,      -- person, organization, product, project, lead
    name VARCHAR(255) NOT NULL,
    aliases TEXT[] DEFAULT '{}',            -- 别名列表，用于实体消歧
    properties JSONB DEFAULT '{}',          -- 灵活属性 (title, phone, email, etc.)
    embedding vector(1536),                 -- 语义向量，用于模糊匹配
    source VARCHAR(50) DEFAULT 'agent',     -- agent, import, crm_sync
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, entity_type, name)
);

-- 关系表：实体间的有向关系
CREATE TABLE IF NOT EXISTS graph_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL,
    source_entity_id UUID NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL,     -- reports_to, belongs_to, sells_to, contacts
    properties JSONB DEFAULT '{}',          -- weight, since, notes
    confidence FLOAT DEFAULT 1.0,           -- 0.0-1.0，自动提取的关系置信度
    source VARCHAR(50) DEFAULT 'agent',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, source_entity_id, target_entity_id, relation_type)
);

-- 索引
CREATE INDEX idx_graph_entities_tenant_type ON graph_entities(tenant_id, entity_type);
CREATE INDEX idx_graph_entities_name_trgm ON graph_entities USING gin(name gin_trgm_ops);
CREATE INDEX idx_graph_entities_embedding ON graph_entities USING ivfflat(embedding vector_cosine_ops) WITH (lists=100);
CREATE INDEX idx_graph_relations_source ON graph_relations(source_entity_id);
CREATE INDEX idx_graph_relations_target ON graph_relations(target_entity_id);
CREATE INDEX idx_graph_relations_type ON graph_relations(tenant_id, relation_type);
```

### 2.2 实体类型枚举

| entity_type    | 说明         | 典型属性                         |
|----------------|--------------|----------------------------------|
| `person`       | 联系人/员工  | title, phone, email, department  |
| `organization` | 公司/部门    | industry, size, address          |
| `product`      | 产品/方案    | category, price_range            |
| `project`      | 项目/商机    | stage, value, deadline           |
| `lead`         | 销售线索     | stage, source, priority          |

### 2.3 关系类型枚举

| relation_type  | 说明             | 示例                              |
|----------------|------------------|-----------------------------------|
| `reports_to`   | 汇报关系         | 员工A → 经理B                     |
| `belongs_to`   | 归属关系         | 员工A → 部门X                     |
| `contacts`     | 联系人关系       | 销售员 → 客户联系人               |
| `sells_to`     | 销售关系         | 公司 → 客户                       |
| `related_to`   | 通用关联         | 项目A → 产品B                     |
| `competes_with`| 竞争关系         | 产品A → 竞品B                     |

## 3. 存储方案对比

| 维度           | PostgreSQL + pgvector (推荐) | Neo4j                        |
|----------------|------------------------------|------------------------------|
| 部署复杂度     | 零额外依赖（已有 Supabase）  | 需要独立实例，增加运维成本   |
| 学习成本       | 标准 SQL + 递归 CTE          | Cypher 查询语言              |
| 向量搜索       | pgvector 原生支持            | 需插件（neo4j-vector）       |
| 多跳遍历性能   | 3 跳内够用（递归 CTE）       | 深度遍历优势明显             |
| 事务一致性     | 与业务表同库，强一致          | 跨库需分布式事务             |
| 成本           | 包含在 Supabase 套餐内       | 额外 $50-200/月              |

**结论**：推荐 PostgreSQL 原生方案。CRM 场景中关系深度通常 <=3 跳，PostgreSQL 递归 CTE 足够满足性能需求，且避免引入新基础设施依赖。

## 4. 与现有 memory.py 的集成点

### 4.1 写入时机

在 `memory.py` 的 `save_to_memory()` 方法中，对话结束后：

1. 调用 LLM 从对话中提取实体和关系（类似现有的 `_extract_with_llm`）
2. 通过 `GraphMemoryService.upsert_entities()` 写入实体
3. 通过 `GraphMemoryService.upsert_relations()` 写入关系

```python
# memory.py 集成伪代码
async def save_to_memory(self, ...):
    # 现有逻辑：保存对话记忆
    await self._save_conversation_memory(...)

    # 新增：提取并保存图谱实体/关系
    entities, relations = await self._extract_graph_data(messages)
    if entities:
        await graph_memory_service.upsert_entities(tenant_id, entities)
    if relations:
        await graph_memory_service.upsert_relations(tenant_id, relations)
```

### 4.2 读取时机

在 `memory.py` 的 `prepare_context()` 方法中，构建 Agent 上下文时：

1. 从用户查询中识别实体名称
2. 查询图谱获取 1-2 跳关联实体和关系
3. 将图谱上下文拼接到 RAG 上下文中

```python
# memory.py 集成伪代码
async def prepare_context(self, query: str, ...):
    # 现有逻辑：检索 RAG 上下文
    rag_context = await self._retrieve_rag(query)

    # 新增：检索图谱上下文
    graph_context = await graph_memory_service.query_context(
        tenant_id, query, max_hops=2
    )
    if graph_context:
        rag_context = f"{rag_context}\n\n[关系图谱]\n{graph_context}"
```

## 5. 查询示例

### 5.1 查找某人的上下级（递归 CTE）

```sql
-- 查找张总的所有下属（2跳以内）
WITH RECURSIVE subordinates AS (
    -- 起点
    SELECT e.id, e.name, e.properties, 0 AS depth
    FROM graph_entities e
    WHERE e.tenant_id = $1 AND e.name = '张总' AND e.entity_type = 'person'

    UNION ALL

    -- 递归：找汇报给当前节点的人
    SELECT e2.id, e2.name, e2.properties, s.depth + 1
    FROM subordinates s
    JOIN graph_relations r ON r.target_entity_id = s.id AND r.relation_type = 'reports_to'
    JOIN graph_entities e2 ON e2.id = r.source_entity_id
    WHERE s.depth < 2
)
SELECT * FROM subordinates WHERE depth > 0;
```

### 5.2 查找与某客户相关的所有实体

```sql
-- 华为相关的联系人、线索、项目（1跳）
SELECT
    e2.entity_type,
    e2.name,
    r.relation_type,
    e2.properties
FROM graph_entities e1
JOIN graph_relations r ON (r.source_entity_id = e1.id OR r.target_entity_id = e1.id)
JOIN graph_entities e2 ON e2.id = CASE
    WHEN r.source_entity_id = e1.id THEN r.target_entity_id
    ELSE r.source_entity_id
END
WHERE e1.tenant_id = $1
  AND e1.name ILIKE '%华为%'
  AND e1.entity_type = 'organization';
```

### 5.3 语义模糊匹配实体

```sql
-- 用向量相似度找到最匹配的实体（处理"华为"vs"华为技术有限公司"）
SELECT id, name, entity_type, 1 - (embedding <=> $2) AS similarity
FROM graph_entities
WHERE tenant_id = $1
  AND 1 - (embedding <=> $2) > 0.7
ORDER BY embedding <=> $2
LIMIT 5;
```

## 6. GraphMemoryService API 设计

```python
class GraphMemoryService:
    """轻量级图谱记忆服务"""

    async def upsert_entities(
        self, tenant_id: str, entities: list[dict]
    ) -> list[str]:
        """批量创建/更新实体，返回实体 ID 列表"""

    async def upsert_relations(
        self, tenant_id: str, relations: list[dict]
    ) -> list[str]:
        """批量创建/更新关系"""

    async def query_neighbors(
        self, tenant_id: str, entity_name: str,
        max_hops: int = 2, relation_types: list[str] | None = None
    ) -> list[dict]:
        """查询实体的 N 跳邻居"""

    async def query_context(
        self, tenant_id: str, query: str, max_hops: int = 2
    ) -> str:
        """从查询中提取实体，返回格式化的图谱上下文字符串"""

    async def search_entities(
        self, tenant_id: str, query: str, entity_type: str | None = None,
        limit: int = 5
    ) -> list[dict]:
        """语义 + 文本模糊搜索实体"""

    async def merge_entities(
        self, tenant_id: str, source_id: str, target_id: str
    ) -> None:
        """合并重复实体（实体消歧后）"""
```

## 7. 实施路线图

### Phase 1: 基础建设（1-2 周）

- [ ] 创建 `graph_entities` 和 `graph_relations` 表的 migration
- [ ] 实现 `GraphMemoryService` 核心 CRUD 方法
- [ ] 添加 pg_trgm 扩展支持模糊文本匹配
- [ ] 单元测试：实体/关系的增删改查

### Phase 2: 自动提取（2-3 周）

- [ ] 实现 LLM 实体/关系提取 prompt（复用 `_extract_with_llm` 模式）
- [ ] 集成到 `memory.py` 的 `save_to_memory()` 流程
- [ ] 实体消歧逻辑（向量相似度 + 别名匹配）
- [ ] 集成测试：对话 → 图谱写入

### Phase 3: 上下文增强（1-2 周）

- [ ] 实现 `query_context()` 方法（递归 CTE 查询 + 格式化输出）
- [ ] 集成到 `prepare_context()` 流程
- [ ] A/B 测试：对比有无图谱上下文的 Agent 回答质量
- [ ] 性能基准测试（目标：< 50ms 查询延迟）

### Phase 4: 工具暴露（1 周）

- [ ] 创建 `query_org_chart` 工具供 Agent 显式调用
- [ ] 创建 `query_entity_relations` 工具
- [ ] 前端可视化组件（可选：gen-ui 图谱卡片）

## 8. 风险与缓解

| 风险                         | 缓解措施                                  |
|------------------------------|-------------------------------------------|
| LLM 提取实体不准确           | 设置 confidence 阈值，低置信度不入库      |
| 实体重复（同一实体多种写法） | 向量相似度 + 别名表自动合并               |
| 图谱膨胀导致查询变慢         | 定期清理低 confidence 关系，限制 max_hops |
| 递归 CTE 在深层遍历性能下降  | 限制最大深度 3 跳，加物化视图             |

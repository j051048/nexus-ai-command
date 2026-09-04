# 知识图谱时间有效性与时间旅行 (Temporal Knowledge Graph)

## 概述
Nexus AI 现已支持知识图谱的三元组时间有效性追踪。这意味着系统不仅记录“实体 A 与实体 B 的关系”，还记录该关系在“何时”有效。

通过引入 `valid_from` 和 `valid_to` 字段，我们实现了：
1. **自动冲突解决 (Soft Expiration)**：当新事实与现有事实冲突时，旧事实会自动标记为过期，而非物理删除。
2. **时间回溯查询 (Time Travel)**：可以查询任意历史时间点系统所掌握的知识状态。
3. **知识演变追溯**：完整记录实体关系的变化轨迹。

## 技术实现

### 数据库模式
`knowledge_graph_triples` 表新增字段：
- `valid_from`: 三元组生效的时间点 (TIMESTAMPTZ)。
- `valid_to`: 三元组失效的时间点 (TIMESTAMPTZ)。若为 `NULL`，表示当前仍然有效。

### 核心接口

#### 1. 存储三元组 (带有冲突检测)
在 `app.services.conversation_memory.graph_extraction._store_triples` 中实现。
- 当插入 `(S, R, D_new)` 时，如果已存在 `(S, R, D_old)` 且 `D_old != D_new`，系统会将 `D_old` 的 `valid_to` 设置为当前时间。

#### 2. 时间查询
通过 `app.services.conversation_memory.graph_extraction.query_entity_at_time` 实现。
```python
results = await query_entity_at_time(
    org_id="...",
    entity_name="张三",
    target_time="2025-01-01T12:00:00Z"
)
```

### RLS 策略
三元组表受 Row Level Security (RLS) 保护：
- 所有读写必须匹配数据库会话解析出的 `organization_id`，防止跨组织访问。
- 表中仍保留 owner、visibility 和角色细粒度策略，但后续租户策略补全迁移还增加了同组织 `FOR ALL` 策略；当前不能宣称数据库已强制“仅本人或经理可修改”。
- API 与 Agent 工具必须继续执行角色授权，生产前应按 `docs/handbook/09-known-debt.md` 收敛重叠策略。
- 后端 Service Role 只能在已验证的组织上下文中使用，不能把客户端传入的组织标识直接视为可信。

## 示例场景
1. **职位变动**：
   - 2024年："张三" - "职位" -> "后端工程师"
   - 2025年："张三" - "职位" -> "架构师"
   - 回溯查询 2024 年的数据，系统依然能准确回答“当时张三负责后端开发”。

2. **项目归属**：
   - 追踪项目经理的变更，了解历史责任边界。

## 故障排除
如果发现查询结果为空，请检查：
- `valid_from` 是否晚于您的查询时间。
- 实体名是否使用了别名（系统支持自动别名解析，详见 `entity_resolution.py`）。
- `20260409_kg_temporal_validity.sql` 及后续 RLS 修复迁移是否已执行。
- 请求是否携带正确的认证和组织上下文，且记录可见性允许当前用户读取。
- 需要自动抽取新三元组时，再检查 `.env` 中的 `AI_BASE_URL`、`OPENAI_API_KEY` 和强制模型是否可用。

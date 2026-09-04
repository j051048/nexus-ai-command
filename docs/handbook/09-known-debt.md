# 已知技术债

## 当前受控债务

- 前端仍有若干超过 500 行的历史页面和 Hook；`check_source_size.mjs` 记录逐文件上限，禁止增长。
- 后端存在历史宽泛异常捕获；`check_exception_governance.py` 记录基线，只允许下降。
- `app/services` 领域边界尚未完全物理拆分；采用 registry + 触碰即迁移策略。
- 全量真实黄金路径依赖 staging Supabase、Redis 和 LLM，普通 PR 主要运行离线契约。
- 测试覆盖率仍是阶段基线，不应把整体百分比当作关键路径质量的替代品。
- `knowledge_graph_triples` 同时存在细粒度 owner/role 策略和后续同组织 `FOR ALL` 策略；宽松策略按 OR 组合，生产前需用新迁移收敛为明确的按操作授权并补越权回归测试。

## 偿还原则

优先修复会造成租户泄露、数据损坏、重复扣费、Agent 错误执行和不可恢复发布的债务。纯粹为了目录整齐的大规模重写优先级较低。

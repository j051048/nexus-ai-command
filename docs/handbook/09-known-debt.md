# 已知技术债

## 当前受控债务

- **租户查询范围**：`docs/quality/tenant-query-scope-baseline.json` 记录 752 处未带组织条件的 `.table()` 调用（186 个文件）。`get_org_filtered_client` 目前只有 13 处使用。这是当前最大的企业级风险，门禁只冻结存量；收敛必须按领域推进并补越权回归测试。
- **前端源文件体积**：仍有 40 个超过 500 行的历史页面与 Hook；`check_source_size.mjs` 逐文件冻结上限，禁止增长。`src/lib/i18n.ts` 及 4 个 locale 文件已作为死代码删除（此前只被 `App.tsx` 包裹但无任何翻译调用）。
- **后端源文件体积**：`docs/quality/backend-source-size-baseline.json` 记录 46 个超过 700 行的 `app` 文件；新增文件不得越过阈值。
- **宽泛异常捕获**：`check_exception_governance.py` 基线 1850 处、显式豁免 35 处，两者都只允许下降。豁免标记本身受上限约束，不能当作逃生通道。
- **直接读取环境变量**：`docs/quality/config-access-baseline.json` 记录 `app/core` 之外的 111 处 `os.getenv/os.environ`（36 个文件），只允许下降；新配置必须走 `app/core/config.py`。
- `app/services` 领域边界尚未完全物理拆分；采用 registry + 触碰即迁移策略。
- **全量真实黄金路径依赖 staging Supabase、Redis 和 LLM**，普通 PR 主要运行离线契约。`nexus_backend/evals/artifact_output_baseline.json` 的 `source` 目前是 `contract-fixture`，验证的是评测器契约而不是真实模型质量；升级为 `live-model` 需要凭据环境录制。
- **测试覆盖率仍是阶段基线**，不应把整体百分比当作关键路径质量的替代品；2026-09-21 快照为行 15.50%、分支 11.28%，其中一部分提升来自删除死代码而非新增测试。
- **E2E 套件结构重叠未消除**：`business-flows`、`core-business`、`comprehensive`、`top10-critical-flows`、`authenticated-flows` 语义重叠，单 chromium project、`workers=1`，合并需要一轮专门的测试资产整理。
- **前端智能层路线未完成**：命令栏语义路由强化、GenUI 扩展、页面级 proactive AI 仍在路线中，尚未进入 P0-P2 范围。
- `knowledge_graph_triples` 同时存在细粒度 owner/role 策略和后续同组织 `FOR ALL` 策略；宽松策略按 OR 组合，生产前需用新迁移收敛为明确的按操作授权并补越权回归测试。

## 已在本轮关闭

- 环境隔离：非生产构建缺少 `VITE_API_BASE_URL` 时直接失败，catch-all 路由补齐 CSP 与安全头。
- 部署拓扑：四套部署面边界写入 `docs/adr/005-deployment-topology-authority.md`，k8s 镜像禁止 `:latest`。
- 租户默认列：`base_repository` 的 `tenant_column` 默认值从 `tenant_id` 修正为 `organization_id`，此前默认值会让查询静默不带租户过滤。
- 反馈闭环：补齐 `change_type` 与审批审计字段，学习候选的 `approved`/`rejected` 只能由管理员写入。
- 模板晋升：客户赢单/输单真正折入模板 A/B 与晋升门槛。
- 产物评测：`scripts/run_artifact_output_eval.py` 增加版本化基线与逐用例回归判定，并接入 CI。
- `maybe_single()` 契约回归：`app/core/postgrest_compat.py` 把 postgrest-py ≥0.16 的"零行返回 `None`"（并在其他错误上伪造 `code=204`）恢复成空响应对象。**这个模块是修复而非兼容包袱，删除会同时复活约 150 处调用点的崩溃与错误类别丢失**；升级 postgrest 前先读它的 docstring。
- Redis URL 归一化：`app/core/redis_url.py` 统一补 `redis://` 前缀、拒绝 `http(s)://` 等非法 scheme。生产环境 `REDIS_URL` 写错时，启动期打 CRITICAL、令牌预算降级为进程内计数并登记 degradation，而不是把成本护栏变成全量 AI 中断。真正的修复仍是运维侧改对 `REDIS_URL`。
- `llm_model_config` 数据缺口：`FORCED_CHAT_MODEL=deepseek-v4.1-flash` 在库中没有 enabled 行，网关每次都走 env fallback 并打一条 WARN。补齐需要确认该模型的 base_url/密钥后再写入种子迁移，不能只插空行。

## 偿还原则

优先修复会造成租户泄露、数据损坏、重复扣费、Agent 错误执行和不可恢复发布的债务。纯粹为了目录整齐的大规模重写优先级较低。

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
- **视觉基线仍需人工审阅**：Linux 基线由 nightly 重新基线模式生成，Windows 基线由本机生成，两者都需要维护者看图确认没有把错误页面固化成"正确"；工具无法替代这一步。
- **前端智能层路线未完成**：命令栏语义路由强化、GenUI 扩展、页面级 proactive AI 仍在路线中，尚未进入 P0-P2 范围。
- `knowledge_graph_triples` 同时存在细粒度 owner/role 策略和后续同组织 `FOR ALL` 策略；宽松策略按 OR 组合，生产前需用新迁移收敛为明确的按操作授权并补越权回归测试。

## 已在本轮关闭

- 环境隔离：非生产构建缺少 `VITE_API_BASE_URL` 时直接失败，catch-all 路由补齐 CSP 与安全头。
- 备份执行者：`backup_schedules` 过去只写不读（`app/tasks/backup.py` 是纯日志占位且未注册），现在由 `app/tasks/backup_tasks.py` 每 15 分钟按 `next_backup_at` 比较并交换领取并执行，失败写回 `last_status`/`last_error`；`BACKUP_STORAGE_BACKEND` 可把负载放到文件系统或 S3 兼容对象存储，数据库只留清单与校验和。
- 数据保留执行：`/api/compliance/retention` 曾硬编码 365/90/180 天且无执行者。现在窗口来自配置，`DATA_RETENTION_ENFORCEMENT_ENABLED` 开启后按组织逐个清理并写入 `data_retention_runs`；未开启时接口明确返回 `enforcement_enabled=false`。
- 产物质量证据诚实化：基线 `source` 只允许 `contract-fixture` 或 `live-model`，`--label live-model` 必须带 manifest（模型 id、时延、成本、证据文档、输出 sha256、环境），`scripts/check_artifact_eval_provenance.py` 已接入 CI；质量 SLO 返回值新增 `evidence` 字段，`claims_live_quality=false` 时不得对外承诺模型质量。
- SLO 告警落地：SLO 此前只有目标表和指标埋点，越界只写一行日志。现在 `app/tasks/alert_tasks.py` 每 5 分钟收集降级、Agent 成功率、备份失败、保留清理失败与文档质量 SLO，按 key 去重后投递到 `ALERT_WEBHOOK_URL`，投递与恢复记录在 `ops_alert_events`；有 Prometheus 的环境使用 `ops/alerts/nexus-slo.rules.yml`。
- 视觉回归基线：仓库此前只提交 Windows 基线，Linux CI 上 8 个用例全红；而 nightly 用的 `--update-snapshots=missing` 在 Playwright 里是"写入并失败"，所以生成路径永远不可能变绿。现在 8 个 Linux 基线已提交，nightly 默认改为严格比对，重新基线改成显式输入 `update_visual_baselines=true`，并新增 `npm run check:visual-baselines` 在 PR 阶段拦截单平台提交与孤儿基线。
- 部署拓扑：四套部署面边界写入 `docs/adr/005-deployment-topology-authority.md`，k8s 镜像禁止 `:latest`。
- 租户默认列：`base_repository` 的 `tenant_column` 默认值从 `tenant_id` 修正为 `organization_id`，此前默认值会让查询静默不带租户过滤。
- 反馈闭环：补齐 `change_type` 与审批审计字段，学习候选的 `approved`/`rejected` 只能由管理员写入。
- 模板晋升：客户赢单/输单真正折入模板 A/B 与晋升门槛。
- 产物评测：`scripts/run_artifact_output_eval.py` 增加版本化基线与逐用例回归判定，并接入 CI。
- `maybe_single()` 契约回归：`app/core/postgrest_compat.py` 把 postgrest-py ≥0.16 的"零行返回 `None`"（并在其他错误上伪造 `code=204`）恢复成空响应对象。**这个模块是修复而非兼容包袱，删除会同时复活约 150 处调用点的崩溃与错误类别丢失**；升级 postgrest 前先读它的 docstring。
- Redis URL 归一化：`app/core/redis_url.py` 统一补 `redis://` 前缀、拒绝 `http(s)://` 等非法 scheme。生产环境 `REDIS_URL` 写错时，启动期打 CRITICAL、令牌预算降级为进程内计数并登记 degradation，而不是把成本护栏变成全量 AI 中断。真正的修复仍是运维侧改对 `REDIS_URL`。
- `llm_model_config` 数据缺口：`FORCED_CHAT_MODEL=deepseek-v4.1-flash` 在库中没有 enabled 行，网关每次都走 env fallback 并打一条 WARN。补齐需要确认该模型的 base_url/密钥后再写入种子迁移，不能只插空行。
- 备份的异地存储默认关闭：`BACKUP_STORAGE_BACKEND` 不显式设置时仍是 `database`，备份与主库同生共死。生产环境必须在部署清单里选定 `filesystem` 或 `s3`，否则只有数据库快照那一层保护。
- S3 后端依赖可选包 `boto3`：未安装时 `BACKUP_STORAGE_BACKEND=s3` 会让备份任务失败并写回 `last_status='failed'`（设计如此，不静默回落到主库）。
- `audit_logs` 中 `org_id IS NULL` 的平台级审计行不参与按组织的保留清理，需要平台 owner 单独处理。
- 告警通道依赖 `ALERT_WEBHOOK_URL`：未配置时 sweep 只写台账并记日志，不会有人收到通知；这是"明确未配置"而不是静默失效。
- 文档质量 SLO 告警按组织抽样（默认 25 个/轮），组织数量很大时需要按 owner 分批或改用 Prometheus 规则。

## 偿还原则

优先修复会造成租户泄露、数据损坏、重复扣费、Agent 错误执行和不可恢复发布的债务。纯粹为了目录整齐的大规模重写优先级较低。

# 文档地图

本目录区分“当前权威文档”“运行手册”“专题参考”和“历史快照”。文档中的数量、默认模型或模块范围若与代码冲突，以可执行配置、测试和自动事实清单为准，并在同一变更中修正文档。

## 当前权威文档

| 主题 | 文档 | 权威代码/配置 |
|---|---|---|
| 产品与启动 | `../README.md` | `package.json`、`nexus_backend/app/core/config.py` |
| 架构边界 | `architecture.md`、`handbook/01-system-map.md` | `src/routes`、`nexus_backend/app/domains` |
| UI 设计 | `UI_DESIGN_CONSTITUTION.md`、`../DESIGN.md` | `src/index.css`、`tailwind.config.ts` |
| Agent 生命周期 | `handbook/05-agent-lifecycle.md` | `nexus_backend/app/agent`、`app/tools` |
| 企业知识与成果 | `DOCUMENT_QUALITY_PLATFORM.md` | `knowledge_ingestion_service.py`、`artifact_generation_service.py` |
| 数据库与租户 | `handbook/04-database-and-migrations.md`、`handbook/06-security-and-tenancy.md` | `supabase/migrations` |
| 测试与发布 | `../TEST_STRATEGY.md`、`handbook/07-testing-and-release.md` | `.github/workflows`、测试配置 |
| 客户验收 | `CUSTOMER_ACCEPTANCE_CRITERIA.md` | `featureFlags.ts`、验收脚本与 E2E |
| 生产运行 | `PRODUCTION_LAUNCH_CHECKLIST.md`、`RUNBOOK_SMALL_COMPANY.md` | `.env.production.example`、Dockerfile |

## 工程接管

从 `handbook/00-start-here.md` 开始。工程规模、迁移数量、测试文件数和强制模型只引用 `handbook/generated/inventory.md`；该文件由 `python scripts/generate_handover_inventory.py` 生成，禁止手工维护。

## 专题参考

- Agent 工具：`TOOL_DEVELOPMENT_GUIDE.md`
- 时间知识图谱：`../nexus_backend/docs/TEMPORAL_KNOWLEDGE_GRAPH.md`
- SOC 2 控制证据：`SOC2_CONTROLS.md`
- 私有化连接池：`PRIVATE_DEPLOYMENT_PGBOUNCER.md`
- 数据库回滚：`../supabase/migrations/rollback/README.md`

## 历史与规划

以下文档用于理解当时的判断，不代表当前实现或承诺：

- `audit/nexus_14_dimension_audit_v3.md`
- `p3_business_flow_plan.md`
- `p4_autonomous_growth_plan.md`
- `nexus_backend/docs/DEFERRED_OPTIMIZATIONS.md`

引用历史数字、评分、模块数量或未来计划前，必须重新以当前代码和线上证据核验。

## 更新规则

- 产品入口、默认模块或操作流程变化时，同步更新 README、用户手册和客户验收标准。
- API、Schema、RLS、环境变量或部署流程变化时，同步更新架构、上线检查表和运行手册。
- Agent、知识检索或成果生成变化时，同步更新生命周期、交付质量平台和对应验收用例。
- UI token 或交互约束变化时，以 `UI_DESIGN_CONSTITUTION.md` 为最高优先级，并同步 `DESIGN.md`。
- 提交前运行 `python scripts/check_handover_readiness.py`，确认链接和自动事实清单未漂移。

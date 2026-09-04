# 工程接管入口

## 第一周阅读顺序

1. `README.md`：产品主线与启动命令。
2. `docs/README.md`：权威文档、专题文档与历史快照的边界。
3. `docs/architecture.md`：运行时边界和不变量。
4. `01-system-map.md`：领域、目录和所有权。
5. `04-database-and-migrations.md`：Schema 与租户边界。
6. `05-agent-lifecycle.md`：一次 AI 请求及精品成果如何运行。
7. `docs/DOCUMENT_QUALITY_PLATFORM.md`：企业资料到可下载成果的交付内核。
8. `07-testing-and-release.md`：哪些门禁是真执行，哪些需要外部环境。
9. `09-known-debt.md`：不要把历史债务误判为新设计。

## 30/60/90 天接管目标

- **30 天**：本地跑通前后端、定向测试和“资料入库 -> 方案生成 -> 质量复核 -> 文件下载”黄金路径；轮换所有生产凭据。
- **60 天**：为核心域指定长期 owner；演练迁移、回滚、Agent 降级和租户事故响应。
- **90 天**：按线上数据收敛模块、覆盖率、SLO 和成本目标，而非继续横向加页面。

## 权威来源

- 工程规模：`generated/inventory.md`
- 默认模型：`nexus_backend/app/core/config.py`
- 领域责任：`nexus_backend/app/domains/__init__.py`
- 迁移顺序：`supabase/migrations/*.sql`
- CI 真相：`.github/workflows/ci.yml` 和 `test-full.yml`
- 首发模块：`src/config/featureFlags.ts`
- 成果交付：`nexus_backend/app/services/artifact_generation_service.py`

文档与代码冲突时，以可执行代码和测试为准，并在同一 PR 修正文档。

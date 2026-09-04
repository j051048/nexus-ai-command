# 生产证明体系

`scripts/production_proof_gate.py` 是仓库级静态证明入口。它验证关键实现、数据集、Schema、质量门和 CI 接线仍然存在，但不会伪装成真实数据库、LLM、外部系统或浏览器已经在线跑通。

## 证明域

当前证明覆盖以下不变量，具体检查项以脚本中的 `CHECKS` 为准，不在文档重复维护会过期的数量：

- 黄金业务流、可执行回放与隔离 staging 流程。
- Agent graph、路由评测、循环预算、上下文编译、SSE 恢复与失败归因。
- Tool Catalog、RBAC、HITL、事务/幂等、补偿和成本硬门。
- Schema 迁移重放、checksum 治理、字段收敛、RLS 和跨租户隔离。
- 科学仪器产品域、VMD/增长工作台、客户方案与投标运营闭环。
- 企业知识入库、文档身份召回、混合检索、Graph RAG 与证据契约。
- 精品成果深度生成、质量矩阵、模板/反馈、持久化任务、下载和质量可观测。
- 前端静态质量、覆盖率趋势、视觉/无障碍回归、Docker 构建和供应链安全。
- 工程交接、恢复、SLO、客户成功和发布证据。

## 静态与在线证明

| 模式 | 能证明 | 不能证明 |
|---|---|---|
| 静态 gate | 文件、token、数据集规模、路由/策略接线和离线契约 | 生产凭据、真实 RLS、Provider、队列或下载可用 |
| 录制/回放 | Prompt、工具选择和已知失败不回归 | 当前 Provider 行为和线上数据质量 |
| staging 在线 | 迁移、真实 Agent、RLS、入库、成果生成和下载 | 生产容量与长期稳定性 |
| 生产观察 | SLO、错误预算、成本、采用率和恢复能力 | 尚未发生的极端故障 |

## 推荐命令

```bash
python scripts/production_proof_gate.py
python scripts/check_migration_governance.py
python scripts/check_transaction_contracts.py
python scripts/scan_migration_schema_conflicts.py
python scripts/scan_rls_coverage.py
python scripts/scan_rls_policy_columns.py
python scripts/audit_schema_convergence.py
python scripts/verify_migration_replay.py
python scripts/customer_acceptance_gate.py

cd nexus_backend
pytest tests/production_proof -q
```

Windows 交接可使用：

```powershell
.\scripts\run_last_mile_checks.ps1
.\scripts\run_last_mile_checks.ps1 -RealMigrations -RealBackend
```

## 在线证明

Agent 回放、RLS、迁移重放和客户成果验收各自要求显式凭据。发布负责人必须使用专用测试组织，保存 Commit、环境、数据集版本、起止时间、结果和清理记录。

客户成果端到端证明：

```bash
GOLDEN_ACCEPTANCE_BASE_URL=... \
GOLDEN_ACCEPTANCE_TOKEN=... \
GOLDEN_ACCEPTANCE_ORG_ID=... \
python scripts/run_customer_golden_acceptance.py --require-live
```

该流程上传五类科学仪器 fixture，等待知识入库，创建深度成果任务，并校验 DOCX/PDF 文件签名和最小体积。没有凭据时的 skip 不能用于客户签收。

## 证据保留

每次正式发布保存 gate 输出、测试报告、覆盖率、迁移/RLS 结果、Docker digest、在线黄金路径、SLO 快照和回滚目标。任何质量数字都必须绑定代码版本、数据集和运行模式。

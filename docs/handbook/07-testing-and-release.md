# 测试与发布

## 测试层级

| 层级 | 目的 | 默认网络 |
|---|---|---|
| 单元 | 纯规则、组件和边界条件 | 禁止 |
| 契约 | API、SSE、工具与 Schema 形状 | 禁止 |
| 集成 | 服务 + 测试数据库/录制 LLM | 隔离 |
| E2E | 浏览器到 API 的黄金路径 | staging |
| 生产证明 | 迁移、RLS、容量、恢复与 SLO | 显式启用 |

CI 中的静态 proof 证明“契约存在”，不等同于真实外部系统已跑通。需要密钥的任务若被跳过，发布负责人必须在 staging 补跑并保存证据。

## 发布门禁

```bash
python scripts/check_handover_readiness.py
python scripts/check_exception_governance.py
python scripts/customer_acceptance_gate.py
python scripts/release_quality_gate.py
python scripts/production_proof_gate.py
```

交接时可统一执行 `python scripts/run_handover_proof.py`；加 `--full` 会进一步运行前端测试、构建和后端领域契约。

前端完整本地门禁：

```bash
npm run test -- --coverage
node scripts/check_frontend_coverage_trend.mjs --check
npm run quality:frontend
npx playwright test --project=chromium
```

客户成果在线验收使用 `python scripts/run_customer_golden_acceptance.py --require-live`，覆盖上传、入库、成果任务和 DOCX/PDF 下载。没有 `GOLDEN_ACCEPTANCE_*` 凭据时只能证明静态契约，不能作为在线交付通过证据。

成果交付的验收要求、步骤检查点、预览修订与文件级评测，以及 2026-09-10 的 RLS/移动端修复，见[交付质量记录](../quality/delivery-hardening-20260909.md)。新增迁移必须经过 RLS 覆盖和策略字段检查；后端专用表只能给后端角色策略，不得为通过扫描而向普通用户开放。

发布必须可回滚：前端保留上一构建，后端保持向后兼容一个版本，数据库优先 roll-forward；破坏性回滚需经过数据负责人批准。

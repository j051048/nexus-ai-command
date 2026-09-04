# Nexus AI Command 测试策略

本策略区分“当前阻断门槛”“质量趋势”和“长期目标”。不得把规划中的覆盖率或静态契约描述成已经在线跑通的事实。

## 测试分层

| 层级 | 目的 | 主要位置 | 外部网络 |
|---|---|---|---|
| 前端单元/组件 | 纯规则、Hook、组件状态与错误恢复 | `src/__tests__` | 禁止 |
| 浏览器 E2E | 登录、业务工作区、响应式、无障碍和视觉回归 | `e2e` | 默认使用路由模拟；在线用例显式启用 |
| 后端单元 | Agent、工具、服务、权限和边界条件 | `nexus_backend/tests/unit` | 禁止 |
| 后端集成 | 跨服务、数据库契约、RLS 和任务协作 | `nexus_backend/tests/integration` | 仅测试环境 |
| Agent/Eval | 路由、计划、证据、反思预算和质量回归 | `nexus_backend/tests/agent`、`evals` | 录制或显式在线 |
| 安全/性能/E2E | 租户隔离、提示注入、容量和完整业务流 | 对应测试目录、`tests/k6` | 显式配置 |
| 生产证明 | Schema 重放、黄金路径、在线客户验收和恢复 | `scripts/*gate.py`、`tests/production_proof` | 静态默认，在线显式启用 |

实时测试文件数以 `docs/handbook/generated/inventory.md` 为准，不在本文件维护会过期的数量清单。

## 当前前端覆盖事实

2026-09-04 本地执行 `npm run test -- --coverage`：61 个测试文件、358 个测试全部通过；行 13.69%、语句 13.04%、函数 9.73%、分支 9.74%。这是一次开发机快照，不是 SLA。

当前有两道回归防线：

- `vitest.config.ts` 的硬下限：lines 12.0、branches 7.5、functions 8.0、statements 11.0。
- `scripts/check_frontend_coverage_trend.mjs` 将本次结果与 `docs/test-coverage/frontend-baseline.json` 比较，任何指标下降超过 0.75 个百分点即失败。

详细路线见 `docs/FRONTEND_TEST_COVERAGE.md`。后端主 CI 的整体覆盖阻断线为 30%，下一阶段目标为 45%；风险场景的要求高于整体行覆盖率。

## 风险优先级

P0 必须按场景完整通过：

- 跨租户读取/写入与 Service Role 边界。
- 会员权益、审批、付款、批量外发和权限变更的事务、幂等、审计及 HITL。
- 企业资料上传、租户绑定、入库、检索和来源引用。
- 方案/标书成果的证据约束、质量门、持久化任务及安全下载。
- Agent 工具 RBAC、提示注入、循环预算、失败归因和不可逆动作。
- 空库迁移重放、Schema 收敛、RLS 覆盖和策略字段一致性。

P1 优先保护：SSE 断线恢复、长任务取消/重试、弱网与离线队列、外部集成超时、模型 fallback、成本熔断、移动端关键路径和视觉回归。

## CI 门禁

`.github/workflows/ci.yml` 是 push/PR 主门禁；`.github/workflows/test-full.yml` 是定时和手动全量回归。全量流水线阻断以下失败：

- 前后端静态检查与构建。
- 依赖/秘密扫描、OpenAPI 和 Docker 构建烟测。
- 前端、后端单元、工作流、集成、Agent、安全、性能和 E2E。
- Playwright 全量、视觉回归与无障碍 smoke。
- 覆盖率基线、交接就绪、迁移治理和生产证明。

“静态契约存在”不等于外部系统真实成功。需要 Supabase、LLM 或线上租户的任务如果没有凭据，应清楚标记为 skipped，并在 staging 补跑后保存证据。

## 常用命令

```bash
# 前端
npm run lint
npx tsc --noEmit
npm run test -- --coverage
node scripts/check_frontend_coverage_trend.mjs --check
npm run quality:frontend
npx playwright test --project=chromium

# 仓库级治理
python scripts/check_handover_readiness.py
python scripts/customer_acceptance_gate.py
python scripts/release_quality_gate.py
python scripts/production_proof_gate.py

# 后端
cd nexus_backend
ruff check app/
black --check app/
pytest tests/unit -q
pytest tests/integration -q
pytest tests/agent tests/security -q
pytest tests/production_proof -q
```

在线客户黄金验收需要专用测试租户和三项环境变量：

```bash
GOLDEN_ACCEPTANCE_BASE_URL=... \
GOLDEN_ACCEPTANCE_TOKEN=... \
GOLDEN_ACCEPTANCE_ORG_ID=... \
python scripts/run_customer_golden_acceptance.py --require-live
```

## 提测规则

- 修复缺陷必须先补可复现测试，再修实现。
- 新功能至少覆盖成功、校验失败、权限/租户失败和依赖失败；有副作用的功能还要覆盖幂等、取消或补偿。
- 不用更新覆盖率基线掩盖具体回退，不批量添加 coverage ignore。
- Agent 变更必须附数据集版本、前后指标和成本变化；成果生成变更必须附证据忠实度与可下载文件验证。
- UI 变更必须验证桌面、移动、暗色、空态、错误态和长文本，必要时更新视觉基线。

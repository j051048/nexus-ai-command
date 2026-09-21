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

## 后端异步测试隔离

`nexus_backend/pyproject.toml` 设置 `asyncio_default_fixture_loop_scope = "function"`。异步应用夹具、HTTP 客户端与测试默认都按用例创建和清理；`patched_app` 使用 `@pytest_asyncio.fixture()`，避免跨用例共享服务 mock。

模拟健康探针降级时也要使用独立的 `HealthCache`，并在夹具退出时恢复模块单例；只恢复数据库和缓存服务的 mock 不会清除已经写入的健康状态。

不要仅把异步夹具改成 `scope="module"` 或 `scope="session"`：其事件循环的作用域必须覆盖夹具缓存的作用域，否则会在初始化时报 `ScopeMismatch`。确需共享时，应显式设置兼容的 `loop_scope`，并确认客户端、循环绑定资源和清理逻辑都在正确的事件循环上执行，不能通过扩大全局事件循环作用域绕过测试隔离。

修改异步测试配置后，在 `nexus_backend` 目录完整运行以下回归；先不启用失败重试，以便发现状态泄漏：

```bash
ENV=test ALLOW_TEST_NETWORK=0 python -m pytest tests/integration/ tests/e2e/ -q --tb=short -rs
```

这些后端 ASGI 测试会模拟外部服务，不等同于真实模型、生产数据库或浏览器联调。需要真实环境的跳过项必须单独验收。

## 发布门禁

```bash
python scripts/check_handover_readiness.py
python scripts/check_exception_governance.py
python scripts/customer_acceptance_gate.py
python scripts/release_quality_gate.py
python scripts/production_proof_gate.py
```

交接时可统一执行 `python scripts/run_handover_proof.py`；加 `--full` 会进一步运行前端测试、构建和后端领域契约。

### CI 中的工程健康门禁

这些门禁只冻结存量债务，任何一处增长都会让 PR 失败：

| 门禁 | 脚本 | 冻结对象 |
|---|---|---|
| 租户查询范围 | `check_tenant_query_scope.py` | 未带组织条件的 `.table()` 调用（752 / 186 文件） |
| 配置访问 | `check_config_governance.py` | `app/core` 之外的直接环境变量读取（111 / 36 文件） |
| 宽泛异常 | `check_exception_governance.py` | 宽泛捕获总数（1850）与显式豁免（35） |
| 源码体积 | `check_source_size.mjs` | 前端 500 行、后端 700 行以上的逐文件上限 |
| 部署拓扑 | `check_deployment_topology.py` | k8s 镜像 tag 与 `imagePullPolicy`、compose 构建入口 |
| 环境隔离 | `check_env_isolation.mjs` / `check_env_contract.mjs` | 非生产构建的 API 基址、CSP、`.env.example` 契约 |
| Agent 评测 | `agent_eval_regression_gate.py` | 离线 agent eval 低于发布下限 |
| 产物评测 | `run_artifact_output_eval.py` | `artifact_output_baseline.json` 的通过率与逐用例回归 |
| 测试重试预算 | `check_test_retry_budget.py` | CI 中 flaky 重试次数 |

更新任何基线只允许在**债务真实下降**后执行；不得为了让 PR 通过而重写基线。

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

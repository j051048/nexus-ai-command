# 后端测试结构

测试数量持续变化，实时规模见 `../../docs/handbook/generated/inventory.md`，不要在本文件维护手写计数。

## 目录

| 目录 | 责任 |
|---|---|
| `unit` | 纯规则、服务、Agent 节点、工具和边界条件 |
| `integration` | 服务协作、数据库/RLS、任务和 API 契约 |
| `agent` | 路由、计划、执行、反思、记忆与质量评测 |
| `security` | 租户隔离、权限、提示注入、内容与密钥安全 |
| `performance` | 基准、并发、容量和性能预算 |
| `e2e` | 后端完整业务场景 |
| `production_proof` | 离线生产不变量与显式在线证明契约 |
| `k6` | HTTP 容量与小型企业负载脚本 |

默认测试禁止未批准的外部网络。需要 Supabase、LLM 或 staging 的用例必须通过专用环境变量显式启用，且不能把 skip 当作在线通过。

## 常用命令

在 `nexus_backend` 目录运行：

```bash
pytest tests/unit -q
pytest tests/integration -q
pytest tests/agent -q
pytest tests/security -q
pytest tests/performance -q
pytest tests/e2e -q
pytest tests/production_proof -q
pytest tests -v --cov=app --cov-report=term-missing --cov-report=json
```

静态质量：

```bash
ruff check app/
black --check app/
mypy app/core/config.py app/core/rate_limiter.py app/core/token_budget.py
```

仓库级门禁从根目录执行：

```bash
python scripts/customer_acceptance_gate.py
python scripts/release_quality_gate.py
python scripts/production_proof_gate.py
```

测试命名应描述业务不变量。所有写入或外部工具至少覆盖成功、参数错误、权限/租户拒绝、依赖失败和幂等/补偿；知识与成果链路还需覆盖入库失败、证据不足、质量门失败和下载完整性。

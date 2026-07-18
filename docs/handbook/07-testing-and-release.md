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
python scripts/release_quality_gate.py
python scripts/production_proof_gate.py
```

交接时可统一执行 `python scripts/run_handover_proof.py`；加 `--full` 会进一步运行前端测试、构建和后端领域契约。

发布必须可回滚：前端保留上一构建，后端保持向后兼容一个版本，数据库优先 roll-forward；破坏性回滚需经过数据负责人批准。

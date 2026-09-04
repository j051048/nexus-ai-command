# Agent 与平台实现入口

这份文件保留在 `app/core` 供历史链接使用。当前实现已超过早期的简单错误包装、消息裁剪和 WebSocket 示例；不要继续复制旧伪代码。

## 修改前先读

- 系统边界：`../../../docs/architecture.md`
- Agent 生命周期：`../../../docs/handbook/05-agent-lifecycle.md`
- 安全与租户：`../../../docs/handbook/06-security-and-tenancy.md`
- Tool 开发：`../../../docs/TOOL_DEVELOPMENT_GUIDE.md`
- 成果质量：`../../../docs/DOCUMENT_QUALITY_PLATFORM.md`
- 测试策略：`../../../TEST_STRATEGY.md`

## 当前扩展点

| 需求 | 首选入口 | 不应绕过 |
|---|---|---|
| 新业务 API | `app/routers` -> `app/services` | 认证、组织上下文、领域错误 |
| 新 Agent 工具 | `app/tools/registry.py`、`BaseTool.policy` | Tool RBAC、HITL、幂等、审计 |
| Prompt/Context | Prompt artifact、`app/agent/context_compiler.py` | 预算、证据 ID、注入防护 |
| 企业资料检索 | knowledge ingestion、`vector_service.py`、Graph RAG | 文档身份、组织过滤、来源证据 |
| 精品成果 | `artifact_generation_service.py` 和任务服务 | 统一质量门、版本、下载与反馈 |
| 跨表写入 | `app/core/transaction_contracts.py` + PostgreSQL RPC | 原子性和重放策略 |
| 长任务 | Celery + 持久化状态 | Web 进程生命周期 |

## 最低完成标准

1. 输入使用 Pydantic/JSON Schema 验证，错误转换为稳定领域码。
2. 组织来自服务端认证上下文，对象访问再次校验归属，数据库以 RLS 收尾。
3. 工具声明 action、risk、role、idempotency、compensation、evidence 和 offline policy。
4. 外部调用设置超时、有限重试、熔断和结构化失败，不返回原始密钥或堆栈。
5. Agent 变更受 Token、时间、循环和工具集合预算约束，并补 eval/回放。
6. 成果变更必须证明检索证据、质量门、文件可打开和跨租户下载拒绝。
7. 新迁移前向追加，并包含租户列、索引、RLS、策略和隔离测试。

实现完成后按影响范围运行 `TEST_STRATEGY.md` 中的命令，并同步相关权威文档。

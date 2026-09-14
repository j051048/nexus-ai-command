# 企业中台优化交接记录

日期：2026-09-13。范围：在 `6698c853` 的实现基础上补齐调用链、启动流程和回归验证。
本文是本轮交付状态，不代表整个 P0-P2 计划已经完成，也不代表生产可用性或客户成果质量认证。

## 已落地与本地验证

| 工作包 | 本轮实现 | 代码证据 | 状态边界 |
|---|---|---|---|
| P0 租户身份 | L1/L2、上下文引擎、中间件、主动任务传递企业身份；夜间记忆归纳按用户和企业分组；同用户跨企业不复用旧状态 | `app/services/conversation_memory/{retrieval,visibility,consolidation}.py`、`app/tasks/scheduler.py`、`src/hooks/useActivationState.ts` | 定向测试通过，不等于所有工具与旧接口已逐一完成权限审计 |
| P0 上下文预算 | 工具绑定后计算预算，实际模型配置优先于旧缓存；记录裁剪后的提示词快照；必需规则放不下时拒绝发送 | `app/agent/context_compiler.py`、`app/agent/plan/{prompt_builder,plan_node,tool_binding}.py` | Token 数仍有估算余量，不是每个模型的精确计量 |
| P0 业务执行回执 | 关键旧业务处理器先验证操作者，再申请数据库回执；失败进入人工核对状态；内存和 Redis 回声去重 | `app/services/{event_bus,redis_event_bus,business_event_receipts}.py` | 消费侧回执，不是事务性发件箱，也不保证业务端到端恰好一次 |
| P1 知识入库 | 批量导入按企业、所有者和内容检查重复；正文进入统一存储/索引任务；索引前显示处理中，不再直接显示可检索 | `app/routers/documents.py::bulk_import_documents` | 已验证调度调用；未对真实 Storage、Celery 和向量库执行导入联调 |
| P1 经验治理 | 过期、废弃、被替代的记忆不进入检索上下文；个人规则候选不能作为已批准的公司制度；归纳前先隔离企业并解密资料 | `app/services/conversation_memory/{admission,governance,consolidation}.py` | 原始记忆变化后，所有历史衍生摘要的失效传播仍需专项完善 |
| P1 首份交付 | 进度由可访问的资料、索引状态、确认状态和质量就绪成果计算；客户端响应必须匹配用户和企业 | `app/services/activation_readiness_service.py`、`src/hooks/useLaunchReadiness.ts`、`src/components/product/LaunchChecklistPanel.tsx` | 仅检查最近 100 份资料和 20 份个人成果；成果就绪不等于用户下载成功 |
| P1 部署 | PostgreSQL 使用真实 DSN/数据库密码；打开连接池后初始化检查点；成功后才标记持久化；生产失败阻止启动；加密失败不退回明文 | `app/agent/checkpointer.py`、`app/startup/lifespan.py`、`scripts/private_deploy_doctor.py` | 已验证初始化调用顺序和失败处理，未进行真实数据库连接或恢复演练 |
| P2 质量证据 | 增加身份切换、过期记忆、重复事件、导入、首份交付和检查点启动回归测试 | 下方验证命令 | 单测和模拟 API 浏览器验证不能替代真实模型评测 |
| P2 可接管性 | 更新配置示例、自动事实清单和本记录 | `nexus_backend/.env.example`、`docs/handbook/generated/inventory.md` | 完整类型检查仍有存量错误，不能宣称全部 CI 通过 |

上表中的 `app/` 路径均位于 `nexus_backend/`。

## 部署顺序与兼容性

1. 先备份数据库、记录当前应用版本和已应用迁移的校验和。
2. 配置 `DATABASE_URL`，使用数据库提供方给出的准确连接地址。Supabase API 的 `SUPABASE_SERVICE_KEY` 不是 PostgreSQL 密码。标准托管项目也可配置 `SUPABASE_DB_PASSWORD`；自动构造的是 5432 直连地址。自建数据库、IPv4/session pooler 和自定义域名必须提供显式 DSN。
3. 保留原有 `LANGGRAPH_AES_KEY`。不要随意更换，否则旧检查点可能无法解密。已配置加密但初始化失败时，新代码会拒绝启动/创建检查点，而不是写入明文。
4. 核对目标库迁移记录，按顺序应用尚未应用的下列迁移。**本轮没有执行生产 SQL**，不能把历史 dry-run 当成已提交：
   - `20260909_001_artifact_stage_checkpoints.sql`
   - `20260910_001_artifact_stage_checkpoint_policy.sql`
   - `20260911_001_business_event_receipts.sql`
5. 验证 RLS、服务角色权限及真实读写，再发布应用。消费侧回执表/RPC 缺失时，受保护的业务处理器会拒绝执行，不会绕过回执直接写账。
6. 配置外发连接器的 `SOLUTION_CONNECTOR_ALLOWED_HOSTS`。未配置白名单将拒绝外发；服务器仍须使用出站网络规则约束目标，应用层 DNS 检查不能完全消除 DNS rebinding 的检查/连接时差。
7. 以测试企业执行“上传资料 -> 等待可检索 -> 生成方案 -> 核查引用 -> 下载文件 -> 重启后恢复”验收，再开放真实用户流量。

`probe_deployment_dependencies()` 是有超时的只读探测。它验证迁移记录、Redis ping 和检查点查询，不验证工作进程接单、事务恢复、备份可用性或 SLA。

## 回执异常处理

`business_event_receipts` 使用 `(organization_id, event_id, handler)` 作为唯一键。

- `completed`：处理器报告完成；应同时核对业务表结果。
- `needs_attention`：处理器失败，可能已有部分副作用。
- 长时间 `processing`：可能进程退出，不能假设未执行。

人工处理时，使用企业 ID、事件 ID 和处理器名称核对合同、发票或指标记录。**不要删除回执后盲目重放，也不要仅靠 TTL 自动重试**。相同业务操作若生成新的事件 ID，当前回执不能替它自动识别重复业务。后续应把业务写入、事件产生与幂等键收敛到同一数据库事务，并为补偿操作留下独立审计记录。

## 本地验证记录

后端使用 Python 3.11.15、Black 24.10.0，未调用真实模型。

```powershell
# 在 nexus_backend 下执行
.\.venv\Scripts\python.exe -m black --check app/
.\.venv\Scripts\python.exe -m ruff check app/
.\.venv\Scripts\python.exe -m pytest tests/unit/test_enterprise_control_plane.py tests/unit/test_enterprise_scope_regressions.py tests/unit/test_enterprise_ingestion_readiness.py tests/unit/test_prompt_context_harness_convergence.py tests/unit/test_memory_trust_hardening.py tests/unit/test_memory.py tests/unit/test_checkpoint_bootstrap.py tests/unit/test_architecture_guards.py --noconftest -q
```

- 后端定向测试：121 passed。`--noconftest` 隔离全局启动依赖，不属于完整后端集成测试。
- 前端：`useLaunchReadiness`、`httpClient`、`httpClient-edge`、`activationState` 四个测试文件，38 passed。
- 浏览器：`e2e/launch-readiness.spec.ts`，1440px / 390px，2 passed；使用模拟 API，验证索引状态、入口、错误重试与面板溢出。
- `npm run quality:frontend`：通过；包括源码规模、UI 规范、构建、体积和文案检查。源码规模门禁仍报告已登记的大文件债务。
- RLS 覆盖、策略列检查、迁移治理、异常治理、交接就绪检查：本地通过。这些是静态检查，不是线上 RLS 攻击测试。
- **未通过**：`npx tsc -p tsconfig.app.json --noEmit --pretty false` 仍有 114 处存量报错。本轮新增 hook 和请求头回归代码不在报错列表中；未下调门禁或屏蔽全量类型检查。

## 2026-09-14 接口与缓存隔离续作

- 修复 `aiClient` 泛型传递和 nullable signal；保留 `fetch` 原始返回、`get/post/put/delete` 外层包装的兼容契约。
- 统一知识关系、竞品、审批类型/列表/计数和工具元数据的响应解包。错误或无效响应不再在这些 hooks 中被转换成空列表/零计数；知识关系、竞品与审批页面增加局部错误和重试状态。
- 上述查询按企业、用户、角色、平台管理员标志和身份就绪状态区分缓存，请求显式携带企业 ID 和取消信号。身份未就绪时禁止请求；竞品写操作也绑定企业。服务端鉴权仍是安全边界，前端隔离不能替代 RLS 或 ACL。
- 修复自动审批规则把 `aiClient` 当函数调用、从不存在的 `profile.role` 读取权限的问题；规则面板和知识/竞品工作区在身份变化时重建，清理原企业的选择和未提交表单。
- 定向前端测试：5 个文件、52 passed。覆盖响应层级、跨企业/用户/角色缓存、取消与晚返回、未就绪身份、竞品写请求、规则创建/删除/失败重试与切换企业。命令：`npx vitest run src/__tests__/hooks/enterpriseQueryContracts.test.tsx src/__tests__/hooks/useUnifiedApprovals.test.ts src/__tests__/lib/aiClient.test.ts src/__tests__/lib/apiResponse.test.ts src/__tests__/components/AutoApprovalRules.test.tsx`。
- `npm run quality:frontend` 通过；全量 TypeScript 报错由上一轮 114 处降至 **91 处，仍未通过**，未降低 strict 配置。数据库类型缺失 `Relationships`，恢复校验还会暴露未登记表和旧字段，需核对真实 Schema 后统一修复，不能补猜测字段或切换为 `any`。
- 本续作未跑完整前端测试集、完整浏览器回归或真实后端联调，未执行生产 SQL。不要将上一节的浏览器结果视作本续作的浏览器验证。

## 下一批必须完成

1. **P0**：单独清理全量 TypeScript 错误并运行完整前后端 CI；补全服务角色下的知识库目录/共享记忆/后台任务权限审计；不能只依据本轮定向测试宣布安全收敛。
2. **P1**：选一个真实资料源做版本、ACL、增量游标、删除传播与断点恢复；当前批量正文导入不是完整外部连接器。
3. **P1**：选择一条合同或发票链路完成事务性 outbox、业务幂等和人工核对闭环，再推广到其他写操作。
4. **P2**：用获授权的科学仪器资料建立真实成果验收集，记录内容完整性、参数与引用正确性、格式、成本及耗时；完成进程中断和备份恢复演练。

上述内容仍是待办，不能记入本轮已完成项。

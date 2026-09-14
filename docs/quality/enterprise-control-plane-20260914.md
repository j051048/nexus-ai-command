# 企业中台优化续作与验收边界

日期：2026-09-14。接续 `enterprise-control-plane-20260913.md`；本记录覆盖最新代码状态，旧记录中的 TypeScript 未通过和待办描述应结合本记录阅读。

## 已完成的代码改动

| 范围 | 本地实现 | 证据 |
|---|---|---|
| P0 数据契约与类型 | 使用实际数据库 OpenAPI 列元数据生成前端 34 张表的契约，修复全量应用类型错误；CI 改为显式检查应用项目 | `scripts/generate_supabase_contract.py`、`src/integrations/supabase/database-tables.ts`、`package.json::typecheck` |
| P0 主动消息 | 历史消息按企业与用户读取；WebSocket 消息先校验身份，实时和持久化通道共享事件 ID 去重；不再依赖不存在的 `proactive_messages` 表 | `src/components/ai/chat/persistedProactiveMessages.ts`、`src/lib/proactiveMessageStore.ts`、`src/hooks/useWebSocketPush.ts`、`nexus_backend/app/services/agent_result_pusher.py` |
| P0 目录与原始记忆 | 服务角色读取知识目录也按企业、所有者、部门过滤；全局模板不暴露其他企业文档数量；记忆增删改和淘汰带所有者与企业约束 | `nexus_backend/app/services/knowledge_access_service.py`、`nexus_backend/app/routers/documents.py`、`nexus_backend/app/services/conversation_memory/storage.py` |
| P0 写入失败关闭 | 仅明确的 RPC 缺失码允许进入旧迁移兼容路径；权限错误即使含有 `function` 或 `schema cache` 也必须原样拒绝，不再触发备用写入 | `nexus_backend/app/services/conversation_memory/storage.py`、`nexus_backend/tests/security/test_security_multi_tenant.py` |
| P1 衍生记忆有效性 | 来源缺失、变更、过期、权限变化时，不再把历史摘要注入上下文；指纹覆盖整个模型输入批次，不只相信模型自行声明的引用索引 | `nexus_backend/app/services/conversation_memory/lineage.py`、`retrieval.py`、`consolidation.py` |
| P1 记忆失败恢复 | 归纳插入失败或无返回记录时不标记来源已处理；画像先写新结果，再按写入前的旧 ID 快照清理，清理失败仍保留新结果；关系写入验证双方身份 | `nexus_backend/app/services/conversation_memory/consolidation.py`、`nexus_backend/tests/unit/test_memory_consolidation_recovery.py` |
| P2 成果验收 | DOCX/PDF 使用生产解析器检查正文、标题和必需内容；DOCX 额外检查标题层级和表格；任务完成但质量未就绪不能通过 | `scripts/run_customer_golden_acceptance.py`、`nexus_backend/app/services/artifact_export_validation.py` |
| P2 验收证据 | 五个谱系/电子仪器样本均设置 3000 字符下限；记录样本与文件 SHA-256、任务/成果 ID、耗时和逐项失败；上传前验证服务端解析的企业身份 | `nexus_backend/evals/datasets/customer_delivery_acceptance.json`、`.github/workflows/nightly-agent-quality.yml` |
| P2 发布检查 | 用真实交付进度、身份校验、资料权限及浏览器回归契约替换旧首周打卡文案/localStorage 键检查；未降低门禁阈值 | `scripts/release_quality_gate.py` |

数据库契约仅描述列结构，不伪造外键关系；RPC 签名仍需单独维护。生成器默认离线，不接触业务记录。

## 验证结果

- 后端完整单元测试：**1589 passed，1 skipped**；使用正常 `conftest.py` 与网络隔离，不调用真实模型。
- 后端安全测试：**189 passed**，包括权限拒绝、Prompt 注入、企业/角色矩阵与 XSS/CSRF；模拟 RLS 错误传播测试不等于真实数据库 RLS 验证。
- 前端当前配置的完整 Vitest 测试：**430 passed**。
- `npm run quality:frontend`：通过，包含应用 TypeScript、源码规模、UI、构建、体积与文案检查。已登记的大文件债务仍存在，并非所有文件均小于 500 行。
- `black --check app/`：622 文件无需修改；`ruff check app/`：通过。
- 数据契约离线检查通过；生成器自身单测 2 项通过。
- Chromium 浏览器：**6 passed**，覆盖首次交付进度、成果预览与修订、390px/1440px 及跨尺寸切换；查看了桌面和手机截图。这些用例使用模拟 API。
- RLS 覆盖和策略列静态扫描、迁移治理、事务契约检查、异常治理通过。不能据此宣称真实数据库隔离或灾难恢复已验收。

工具恢复单测曾残留 Redis 后台任务，现仅在该单测文件关闭传输同步；生产熔断器逻辑未改动。随后完整后端单测正常退出。

## 迁移与发布

**本轮没有执行生产 SQL，没有提交或推送 Git。**

新增迁移 `supabase/migrations/20260914_001_memory_lineage.sql` 随上一提交进入仓库，但未在本次工作中应用到目标库：

1. 先备份，核对已应用迁移及校验和；在隔离测试库验证迁移、权限、触发器和回滚方案。
2. 应用迁移后检查 `memory_consolidations.source_fingerprints`、`invalidated_at` 及来源更新/删除触发器。
3. 发布应用，验证用户和企业之间的检索、修改、删除隔离。
4. 旧摘要没有来源指纹会暂时不进入上下文，原始有效记忆仍可检索；重新归纳后恢复。迁移将旧摘要的来源恢复为可归纳状态。
5. 若迁移尚未应用，新增摘要写入会报错并保留待重试来源，不会静默宣告归纳成功。

画像更新采用先写后清理，不是数据库事务性 upsert。崩溃可能留下多条画像；读取选择最新记录且重新核验来源。不能宣称归纳与所有来源更新已经原子化或恰好执行一次。

## 本地命令

```powershell
# 仓库根目录；以下命令不访问生产数据库
npm run quality:frontend
npx vitest run
nexus_backend/.venv/Scripts/python.exe scripts/generate_supabase_contract.py --check
nexus_backend/.venv/Scripts/python.exe scripts/check_handover_readiness.py
nexus_backend/.venv/Scripts/python.exe scripts/release_quality_gate.py
npx playwright test e2e/launch-readiness.spec.ts e2e/artifact-delivery-workspace.spec.ts --project=chromium

# nexus_backend 目录
.\.venv\Scripts\python.exe -m black --check app/
.\.venv\Scripts\python.exe -m ruff check app/
.\.venv\Scripts\python.exe -m pytest tests/unit/ -q
```

需要刷新列契约时使用 `python scripts/generate_supabase_contract.py --refresh --env nexus_backend/.env`。此操作只读取 Schema 元数据，生成文件必须人工审查后提交；不要把环境文件或密钥加入 Git。

## 真实成果验收

只对授权的隔离测试企业配置 `GOLDEN_ACCEPTANCE_BASE_URL`、`GOLDEN_ACCEPTANCE_TOKEN`、`GOLDEN_ACCEPTANCE_ORG_ID`，再运行：

```powershell
nexus_backend/.venv/Scripts/python.exe scripts/run_customer_golden_acceptance.py --require-live --output dist/customer-golden-acceptance.json
```

此命令会上传测试样本、创建成果任务并消耗模型费用，不是只读探测。不能对真实客户企业随意运行。缺少凭据时不生成伪造的成功报告；`--require-live` 返回非零。

报告证明格式和基础内容契约，不自动证明参数真实性、政策适用性、引用忠实度或商业效果。五份样本是明确标识的合成资料，不能冒充真实客户黄金集；仍需行业专家盲评与真实资料授权。

## 尚未完成

1. **P0**：旧接口/工具的全面权限审计尚未完成；本轮目录与记忆修复不能等同全产品多租户安全认证。发票接口还存在模型字段与实际表结构不一致，须专门收敛写入契约。
2. **P1**：合同/发票的事务性 outbox、业务幂等与人工核对闭环仍未完成。现有消费回执不是 outbox；不得对结果不明的财务事件盲目自动重放。
3. **P1**：真实外部资料连接器的版本、ACL、游标、删除传播与断点恢复未完成。记忆来源指纹不能替代原文权限变更到全部索引/副本的传播。
4. **P2**：未运行真实模型成果验收、完整浏览器套件、生产容量压测或备份恢复演练。未配置隔离数据库，因此没有真实验证本次迁移触发器。

优先完成上述已有主链路的风险收敛，不追加新的横向功能；不以功能数量或静态门禁通过推导“综合 9 分”或生产 SLA。

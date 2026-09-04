# Nexus AI Command 生产上线检查表

本清单面向首个 20-50 人科学仪器企业部署。环境变量以 `.env.production.example` 和 `nexus_backend/.env.example` 为准，模块范围以 `src/config/featureFlags.ts` 为准，迁移数量以自动事实清单为准。

## P0：开放访问前必须完成

1. **生产凭据**
   - 配置 Supabase URL、Service Role、JWT/JWKS、Redis、加密密钥和至少 24 位健康检查令牌。
   - 配置一个确实提供 `deepseek-v4-flash` 的 OpenAI-compatible 网关；后端会忽略其他聊天模型覆盖值。
   - 所有密钥进入部署平台 Secret，不写入仓库、构建日志或前端变量。

2. **数据库与租户**
   - 从仓库根目录 `supabase/migrations` 按文件名顺序执行正向迁移；不要使用旧的 `nexus_backend/supabase_migrations` 路径。
   - 先在空白测试库重放，再执行 Schema、冲突和 RLS 扫描。
   - 常规托管部署使用部署流水线或 Supabase CLI 推送迁移；`AUTO_MIGRATE` 只用于明确受控、镜像内包含迁移文件的私有部署。

3. **持久化运行时**
   - 设置 `LANGGRAPH_CHECKPOINTER=postgres`。
   - 部署 Redis、Celery Worker 和唯一逻辑 Beat；验证知识入库与成果任务队列。
   - Web、Worker 和 Beat 使用同一版本、同一数据库与兼容的队列配置。

4. **首发模块**
   - 使用 `VITE_LAUNCH_PROFILE=small_company`，默认开放 CRM、审批、竞品、企业资料/知识、项目、报表、销售、投标和 VMD。
   - 保持 `dev_tools` 关闭；财务、HR、OA、库存、计费、插件和设计器仅在客户明确需要且有 owner 时开放。
   - 关闭生产演示数据：`VITE_ENABLE_DEMO_DATA=false`。

5. **安全与成本**
   - CORS 只允许精确生产域名，Service Role 永不进入浏览器。
   - 保持生产 Token 预算 fail-closed；设置租户并发、单请求、每日和每月成本上限。
   - 验证审批、会员、权限、批量外发和删除均有审计、幂等和人工确认。

6. **构建与容器**
   - 从仓库根目录部署 PaaS 时使用根 `Dockerfile`；以 `nexus_backend` 为构建上下文时使用其目录内 `Dockerfile`。
   - Python 包索引不可达时构建会失败，不要把网络错误误判成依赖版本不存在。
   - 前端使用 `npm ci` 和 `npm run build`；不要在生产容器启动时安装依赖。

7. **健康与门禁**

```bash
npm run quality:frontend
python scripts/check_handover_readiness.py
python scripts/customer_acceptance_gate.py
python scripts/release_quality_gate.py
python scripts/production_proof_gate.py
python scripts/check_migration_governance.py
python scripts/check_transaction_contracts.py
python scripts/scan_rls_coverage.py
python scripts/scan_rls_policy_columns.py
python scripts/audit_schema_convergence.py
```

部署后验证公共 `/health`、带 `X-Health-Token` 的 `/health/deep` 和管理员 `/api/system/deployment-health`。

8. **业务黄金路径**
   - 用目标组织真实测试资料跑通：上传 -> 入库 ready -> AI 检索 -> 方案/投标 -> 质量复核 -> DOCX/PDF 下载。
   - 使用 `run_customer_golden_acceptance.py --require-live` 留存在线证据。
   - 再验证 CRM 跟进、审批、审计日志和跨租户拒绝。

## P1：客户首周必须完成

1. 配置 Sentry、OpenTelemetry/Langfuse 或等价观测，告警覆盖 5xx、认证、队列积压、成果失败和成本异常。
2. 建立每日数据库备份，并在隔离 staging 完成一次恢复演练。
3. 与客户确认资料分类、可信来源、企业模板、品牌规范、外发审批人和禁止自动承诺的条款。
4. 每日检查企业资料入库失败、低证据覆盖成果、质量门失败、工具失败与 Token 异常。
5. 只对真实要用的集成配置生产凭据；未配置的集成应 fail closed 并显示可操作提示。
6. 记录首份方案/标书的生成耗时、人工修改量、采用结果和客户反馈，作为后续质量基线。

## 发布记录

每次生产发布必须保存版本/Commit、迁移清单、门禁输出、健康检查、在线黄金路径、负责人、观察窗口和回滚目标。静态契约通过不能替代在线结果。

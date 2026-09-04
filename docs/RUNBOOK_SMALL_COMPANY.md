# 小型企业生产运行手册

本手册适用于 20-50 人科学仪器企业的 `small_company` 部署。

## 每日检查

1. 检查 `/health`、`/health/deep` 和 `/api/system/deployment-health`。
2. 检查新 5xx、认证/RLS 拒绝异常和前端全局错误。
3. 检查 Redis、Celery Worker/Beat、队列最老任务以及知识入库/成果任务健康。
4. 检查资料入库失败、成果质量门失败、下载失败和最常见工具错误。
5. 检查租户级 LLM 成本、并发、fallback、反思循环和预算拒绝。
6. 确认最新数据库备份存在且对象存储/成果文件保留策略正常。

## 每周检查

1. 将最新备份恢复到隔离 staging，验证用户、组织、审计、文档、向量/检索记录和成果元数据。
2. 运行登录、跨租户拒绝、CRM、资料上传/检索、方案/投标、审批、成果下载和管理员审计黄金路径。
3. 复盘低证据覆盖、人工大改、未采用、输单和失败成果，禁止未经审核样本自动进入模板。
4. 检查新开放模块使用率；没有 owner、没有真实凭据或反复失败的模块应关闭。
5. 检查依赖安全、迁移漂移、RLS coverage、备份恢复时间和密钥轮换记录。

## 事件处理

| 事件 | 立即动作 | 恢复验证 |
|---|---|---|
| AI Provider 故障 | 切换已审批 fallback；降低复杂路径；保留高风险 HITL | 简单问答、资料检索、成果任务和成本记录 |
| 成本突增 | 收紧租户并发、单请求/日/月预算；定位 scene/agent/tool | 成本下降且无跨租户影响 |
| Redis/Worker 故障 | 暂停新增长任务；恢复队列与唯一 Beat | 无重复外发/扣费，旧任务可重试或取消 |
| 资料可见但检索不到 | 核对 ingestion、组织、文档 ID、chunk 和检索证据 | 按文件名与语义都能命中正确文档 |
| 成果无法生成/下载 | 核对 job、质量失败码、Worker、存储与权限 | DOCX/PDF 可打开，成果中心可再次下载 |
| Supabase/RLS 风险 | 停止邀请和高风险写入，保存日志，确认受影响组织 | 两租户隔离测试、数据完整性与审计链 |
| 前端坏包/白屏 | 回滚上一已知构建并清理错误缓存 | 登录、核心工作区、助手和下载入口 |

任何事件先关联 `trace_id`；知识/成果事件同时记录 `organization_id`、`document_id`、`artifact_id/job_id` 和版本。不要在事故中编辑历史迁移。

## 备份与恢复

Linux/macOS：

```bash
DATABASE_URL="postgresql://..." ./scripts/backup_supabase.sh
```

Windows PowerShell：

```powershell
$env:DATABASE_URL="postgresql://..."
.\scripts\backup_supabase.ps1
```

恢复到隔离数据库后，先执行较新的正向迁移，再验证登录、租户隔离、CRM、企业资料、检索、成果、审批和审计。数据库能打开但业务不变量失效，不算恢复成功。

## 模块策略

默认首发：`approval`、`battlecards`、`crm`、`documents`、`knowledge`、`projects`、`reports`、`sales`、`tender`、`vmd`。

按客户验收开放：`custom_dashboard`、`form_designer`、`plugins`、`report_builder`、`soul_document`、`training`、`workflow_designer`、`work_orders`。

优先连接第三方：`assets`、`billing`、`certificates`、`finance`、`hr`、`import`、`inventory`、`oa`。客户环境保持 `dev_tools` 关闭。

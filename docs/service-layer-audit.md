# Service 层数据库客户端审计报告

> 审计日期：2026-03-15
> 审计范围：所有使用 `from app.core.database import supabase` 的文件

## 1. 背景

### 数据库客户端架构

Nexus 后端使用 `MiniSupabaseClient`（轻量 PostgREST 封装），提供两种客户端：

- **全局 `supabase`**（Service Key）：使用 `SUPABASE_SERVICE_KEY`，绕过 RLS，拥有完全数据库访问权限
- **Scoped Client**（User Token）：通过 `supabase.get_scoped_client(token)` 创建，使用用户 JWT，受 RLS 约束

### 风险

当用户面向的操作使用全局 `supabase`（Service Key）时，会绕过 Supabase 行级安全策略（RLS），导致：
- 租户数据隔离失效
- 用户可能访问超出权限的数据
- 合规风险（SOC2 等）

### 依赖注入机制

`dependencies.py` 提供了 `get_db(request)` 函数，从 `request.state.db` 获取 scoped client（由 `TenantContextMiddleware` 注入），全局 `supabase` 作为回退。但**目前没有任何路由端点使用 `Depends(get_db)`**。

---

## 2. 审计结果

### 2.1 Tools 层（Agent 工具函数）

**模式：** 大多数 tools 导入全局 `supabase`，但同时实现了 `_get_client(token)` 辅助函数来获取 scoped client。

| 文件 | 导入方式 | 是否有 scoped 逻辑 | 分类 |
|------|----------|---------------------|------|
| `attendance_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `approval_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `asset_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `approval_flow_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `boss_shared.py` | 全局 import | 有 `_get_client(token)` | OK |
| `certificate_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `contract_crud_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `contract_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `crm_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `expense_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `finance_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `hr_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `ai_insight_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `inventory_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `oa_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `operational_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `organization_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `project_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `strategy_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `system_config_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `vmd_operation_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `vmd_synergy_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `work_order_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `workflow_tools.py` | 全局 import | 有 `_get_client(token)` | OK |
| `scheduled_task_tools.py` | 全局 import | 无 scoped 逻辑 | **NEEDS_FIX** |

### 2.2 Services 层

| 文件 | 导入方式 | 用户面向? | 分类 | 备注 |
|------|----------|-----------|------|------|
| `audit_logger.py` | 全局 import | 否（系统内部） | SAFE | 审计日志写入，需 service key |
| `ai_quality_service.py` | 全局 import | 否 | SAFE | AI 质量监控 |
| `api_key_service.py` | 函数内 import | 部分 | **NEEDS_FIX** | API Key 管理涉及用户数据 |
| `approval_chain.py` | 全局 import | 是 | **NEEDS_FIX** | 审批链操作涉及用户数据 |
| `auto_trigger_service.py` | 函数内 import | 否 | SAFE | 系统自动触发 |
| `bid_service.py` | 全局 import | 是 | **NEEDS_FIX** | 招投标数据，用户可见 |
| `chat_service.py` | 全局 import | 是 | **NEEDS_FIX** | 聊天记录，高敏感 |
| `clue_service.py` | 全局 import | 是 | **NEEDS_FIX** | 线索数据，用户可见 |
| `compliance_service.py` | 全局 import | 否 | SAFE | 合规检查（系统内部） |
| `conversation_memory_service.py` | 全局 import | 是 | **NEEDS_FIX** | 对话记忆，用户私有 |
| `crawler_service.py` | 全局 import | 否 | SAFE | 爬虫服务（后台） |
| `data_export_service.py` | 全局 import | 是 | **NEEDS_FIX** | 数据导出涉及用户数据 |
| `data_import_service.py` | 全局 import | 是 | **NEEDS_FIX** | 数据导入涉及用户数据 |
| `demo_data_service.py` | 全局 import | 否 | SAFE | 演示数据生成 |
| `enterprise_event_handlers.py` | 函数内 import | 否 | SAFE | 事件处理（系统内部） |
| `etl_service.py` | 全局 import | 否 | SAFE | ETL 管道 |
| `event_bus.py` | 函数内 import | 否 | SAFE | 事件总线（系统内部） |
| `failure_log_service.py` | 全局 import | 否 | SAFE | 失败日志记录 |
| `form_schema_service.py` | 全局 import | 是 | **NEEDS_FIX** | 表单定义，租户相关 |
| `health_check_service.py` | 函数内 import | 否 | SAFE | 健康检查 |
| `incentive_service.py` | 全局 import | 是 | **NEEDS_FIX** | 激励/奖励数据 |
| `knowledge_graph_service.py` | 全局 import | 是 | **NEEDS_FIX** | 知识图谱，租户相关 |
| `llm_gateway_service.py` | 全局 import | 否 | SAFE | LLM 网关（系统内部） |
| `llm_helpers.py` | 函数内 import | 否 | SAFE | LLM 辅助函数 |
| `llm_quota_service.py` | 函数内 import | 是 | **NEEDS_FIX** | 用量配额涉及用户 |
| `notification_center_service.py` | 全局 import | 是 | **NEEDS_FIX** | 通知中心，用户可见 |
| `notification_service.py` | 全局 import | 是 | **NEEDS_FIX** | 通知服务 |
| `oauth_service.py` | 函数内 import | 是 | **NEEDS_FIX** | OAuth 涉及用户凭证 |
| `organization.py` | 全局 import | 是 | **NEEDS_FIX** | 组织信息，租户相关 |
| `performance_service.py` | 全局 import | 是 | **NEEDS_FIX** | 绩效数据，用户可见 |
| `permission_service.py` | 全局 import | 是 | **NEEDS_FIX** | 权限服务，安全关键 |
| `push_notification_service.py` | 全局 import | 是 | **NEEDS_FIX** | 推送通知 |
| `scheduled_task_runner.py` | 函数内 import | 否 | SAFE | 定时任务运行器 |
| `semantic_cache.py` | 全局 import | 否 | SAFE | 语义缓存 |
| `smart_recommendation_service.py` | 全局 import | 是 | **NEEDS_FIX** | 推荐服务 |
| `super_admin_service.py` | 函数内 import | 否 | SAFE | 超级管理员（需 service key） |
| `token_service.py` | 函数内 import | 是 | **NEEDS_FIX** | Token 管理，安全关键 |
| `vector_service.py` | 全局 import | 否 | SAFE | 向量化服务 |
| `vmd_report_service.py` | 全局 import | 是 | **NEEDS_FIX** | VMD 报告 |
| `webhook_service.py` | 函数内 import | 否 | SAFE | Webhook 处理 |
| `workflow_definition_service.py` | 全局 import | 是 | **NEEDS_FIX** | 工作流定义 |
| `workflow_template_service.py` | 全局 import | 是 | **NEEDS_FIX** | 工作流模板 |
| `im_platform/attendance_sync_service.py` | 全局 import | 否 | SAFE | IM 考勤同步 |
| `im_platform/contact_sync_service.py` | 全局 import | 否 | SAFE | IM 通讯录同步 |

### 2.3 Routers 层

| 文件 | 导入方式 | 分类 | 备注 |
|------|----------|------|------|
| `im_settings.py` | 全局 import | **NEEDS_FIX** | IM 设置，租户相关 |
| `im_chat.py` | 全局 import | **NEEDS_FIX** | IM 聊天，用户数据 |
| `im_oauth.py` | 全局 import | **NEEDS_FIX** | OAuth 流程 |
| `im_callbacks.py` | 全局 import | SAFE | 回调处理（系统入口） |
| `llm_models.py` | 函数内 import | **NEEDS_FIX** | LLM 模型配置 |
| `memories.py` | 函数内 import | **NEEDS_FIX** | 记忆管理，用户私有 |
| `documents.py` | 全局 import (as global_supabase) | **NEEDS_FIX** | 文档管理 |
| `organization.py` | 函数内 import | **NEEDS_FIX** | 组织管理 |
| `projects.py` | 全局 import | **NEEDS_FIX** | 项目管理 |
| `scheduled_tasks.py` | 全局 import | **NEEDS_FIX** | 定时任务 |
| `vmd_tasks.py` | 函数内 import | **NEEDS_FIX** | VMD 任务 |
| `ws.py` | 函数内 import | SAFE | WebSocket（系统连接管理） |

### 2.4 Agent / Core / Tasks 层

| 文件 | 导入方式 | 分类 | 备注 |
|------|----------|------|------|
| `agent/memory.py` | 全局 import | SAFE | Agent 记忆管理（系统内部） |
| `agent/node_reflect.py` | 函数内 import | SAFE | Agent 反思节点 |
| `agent/proactive_runner.py` | 函数内 import | SAFE | 主动推送运行器 |
| `agent/router.py` | 函数内 import | SAFE | Agent 路由 |
| `agent/roles/registry.py` | 函数内 import | SAFE | 角色注册 |
| `core/api_key_middleware.py` | 函数内 import | SAFE | 中间件（系统内部） |
| `core/dependencies.py` | 全局 import | SAFE | 依赖注入定义 |
| `core/migration_runner.py` | 函数内 import | SAFE | 迁移运行器 |
| `core/schema_validator.py` | 函数内 import | SAFE | Schema 验证 |
| `core/security_middleware.py` | 函数内 import | SAFE | 安全中间件（创建 scoped client） |
| `tasks/scheduler.py` | 函数内 import（多处） | SAFE | 后台调度器 |
| `tasks/event_sensors.py` | 函数内 import（多处） | SAFE | 事件传感器 |
| `main.py` | 函数内 import | SAFE | 应用入口 |

---

## 3. 统计汇总

| 分类 | 数量 | 占比 |
|------|------|------|
| **OK**（已使用 scoped client） | 24 | 28% |
| **SAFE**（系统内部，需要 service key） | 32 | 38% |
| **NEEDS_FIX**（用户面向但用全局 client） | 29 | 34% |

---

## 4. 优先修复清单

### P0 — 安全关键（第 1 周）

1. **`permission_service.py`** — 权限服务使用 service key 意味着所有权限检查绕过 RLS
2. **`token_service.py`** — Token 管理涉及认证安全
3. **`chat_service.py`** — 聊天记录属于高敏感用户数据
4. **`conversation_memory_service.py`** — 对话记忆属于用户私有数据

### P1 — 数据隔离（第 2 周）

5. **`notification_center_service.py`** — 用户可能看到其他租户的通知
6. **`data_export_service.py`** — 数据导出可能跨租户泄露
7. **`organization.py`**（service） — 组织数据需要租户隔离
8. **`performance_service.py`** — 绩效数据高度敏感
9. **`clue_service.py`** — 线索数据涉及业务机密

### P2 — 业务数据（第 3-4 周）

10. **`bid_service.py`** — 招投标数据
11. **`form_schema_service.py`** — 表单定义
12. **`incentive_service.py`** — 激励数据
13. **`knowledge_graph_service.py`** — 知识图谱
14. **`workflow_definition_service.py`** — 工作流定义
15. **`workflow_template_service.py`** — 工作流模板
16. **`vmd_report_service.py`** — VMD 报告
17. **`smart_recommendation_service.py`** — 推荐服务

### P3 — 路由层修复（第 5 周）

18-29. 所有 `routers/` 中标记为 NEEDS_FIX 的文件

---

## 5. 修复方案

### 推荐模式

```python
# 改前（直接使用全局 supabase）
from app.core.database import supabase

class SomeService:
    async def get_user_data(self, user_id: str):
        result = await supabase.table("users").select("*").eq("id", user_id).execute()
        return result.data

# 改后（接受 db client 参数，回退到全局）
from app.core.database import supabase

class SomeService:
    async def get_user_data(self, user_id: str, db=None):
        client = db or supabase
        result = await client.table("users").select("*").eq("id", user_id).execute()
        return result.data
```

### Router 层注入

```python
from app.core.dependencies import get_db

@router.get("/items")
async def list_items(
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    return await some_service.get_items(user_id, db=db)
```

### 注意事项

- `TenantContextMiddleware` 已经在 `request.state.db` 中注入了 scoped client
- `get_db` 依赖已就绪，只需要在路由中使用 `Depends(get_db)` 并传递给 service
- 后台任务（scheduler、event_sensors）使用全局 supabase 是正确的，因为它们是系统级操作
- Tools 层已有 `_get_client(token)` 模式，是良好实践

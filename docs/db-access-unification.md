# 数据库访问层统一设计文档

## 1. 现状分析

### 1.1 问题概述

当前项目中存在两种数据库访问模式：

1. **通过 Service 层**（推荐）：Router -> Service -> Supabase
2. **直接访问**（违规）：Router -> Supabase（跳过 Service 层）

直接访问导致：
- 业务逻辑分散在 Router 层，难以复用
- 租户隔离逻辑重复实现，容易遗漏
- 单元测试困难（需要 mock Supabase 客户端）
- 审计日志、权限检查等横切关注点无法统一处理

### 1.2 Router 层直接访问 Supabase 的违规清单

| Router 文件 | 操作的表 | 违规操作 |
|-------------|---------|---------|
| `documents.py` | `documents`, `document_embeddings` | 删除文档、查询文档、删除嵌入 |
| `im_chat.py` | `im_user_mappings` | 插入/更新 IM 用户映射 |
| `im_callbacks.py` | 多表 | IM 回调处理中的 DB 操作 |
| `im_oauth.py` | 多表 | OAuth 状态存储 |
| `im_settings.py` | 多表 | IM 设置读写 |
| `memories.py` | `users` | 查询用户角色 |
| `organization.py` | `users` | 查询用户组织 ID |
| `projects.py` | `projects`, `users` | 项目的完整 CRUD |
| `ws.py` | `users` | WebSocket 连接时查询用户角色 |
| `scheduled_tasks.py` | 多表 | 定时任务管理 |
| `vmd_tasks.py` | `vmd_main_task` 等 | VMD 任务查询（部分） |
| `llm/_shared.py` | 多表 | LLM 共享查询 |

### 1.3 高风险违规点

1. **`projects.py`**：整个 CRUD 都在 Router 层完成，无 Service 层
2. **`documents.py`**：删除操作直接调用 `global_supabase.table().delete()`，绕过了 Service 层的权限检查
3. **`ws.py`**：WebSocket 握手时直接查询 `users` 表，无租户过滤

## 2. Repository Pattern 迁移方案

### 2.1 架构层次

```
Router (HTTP 层)
    ↓ Depends()
Service (业务逻辑层)
    ↓ 调用
Repository (数据访问层)
    ↓ 封装
Supabase Client (基础设施层)
```

### 2.2 BaseRepository 设计

核心特性：
- 自动注入 `tenant_id` 过滤（多租户隔离）
- 统一的 CRUD 方法（get_by_id, list, create, update, delete）
- 软删除支持（`is_deleted` 字段）
- 分页查询支持
- 类型安全的返回值

完整实现见 `nexus_backend/app/repositories/base_repository.py`。

### 2.3 使用示例

```python
# nexus_backend/app/repositories/project_repository.py
from app.repositories.base_repository import BaseRepository

class ProjectRepository(BaseRepository):
    def __init__(self):
        super().__init__(table_name="projects")

    async def list_active(self, tenant_id: str) -> list[dict]:
        return await self.list(
            tenant_id=tenant_id,
            filters={"stage": ("neq", "archived")},
        )

project_repo = ProjectRepository()
```

```python
# nexus_backend/app/services/project_service.py
from app.repositories.project_repository import project_repo

class ProjectService:
    async def list_projects(self, tenant_id: str, user_role: str):
        projects = await project_repo.list_active(tenant_id)
        # 业务逻辑：非管理员只能看自己的项目
        if user_role != "admin":
            projects = [p for p in projects if p.get("owner_id") == user_id]
        return projects
```

## 3. 迁移策略

### Phase 1：基础设施（已完成）

- [x] 创建 `BaseRepository` 类
- [x] 文档化所有违规点

### Phase 2：高优先级迁移

针对安全风险最高的违规点：

1. **`projects.py`**：创建 `ProjectRepository` + `ProjectService`
2. **`documents.py` 删除操作**：迁移到 `DocumentService`
3. **`ws.py` 用户查询**：使用已有的 auth 服务

### Phase 3：IM 模块统一

1. 创建 `IMRepository` 封装所有 IM 相关表操作
2. 将 `im_chat.py`, `im_callbacks.py`, `im_oauth.py`, `im_settings.py` 中的 DB 操作迁移

### Phase 4：全面迁移

1. 搜索所有 Router 中的 `supabase.table()` 调用
2. 逐个迁移到对应的 Repository + Service
3. 添加 lint 规则禁止 Router 层直接导入 `supabase`

## 4. Lint 规则建议

```python
# .flake8 或 ruff 自定义规则
# 禁止 router 文件中直接导入 supabase
# [project.custom-rules]
# ban-supabase-in-routers = "app/routers/*.py: from app.core.database import supabase"
```

## 5. 注意事项

1. **渐进式迁移**：不要一次性重写所有 Router，按优先级逐步迁移
2. **保持 API 不变**：迁移是内部重构，不改变 HTTP API 契约
3. **测试先行**：迁移前确保有集成测试覆盖，迁移后验证行为一致
4. **Schema 漂移**：Repository 中使用 `select("*")` + Python 端字段映射，参考 MEMORY.md 中的教训

# 模块联邦设计文档 - VMD 子应用拆分方案

## 1. 当前 VMD 相关文件清单

### Routers
| 文件 | 职责 |
|------|------|
| `nexus_backend/app/routers/vmd_tasks.py` | VMD 任务管理（主任务 + 子任务 CRUD） |
| `nexus_backend/app/routers/vmd_clues.py` | VMD 线索管理 |
| `nexus_backend/app/routers/vmd_dashboard.py` | VMD 数据看板 |
| `nexus_backend/app/routers/vmd_compliance.py` | VMD 合规检查 |

### Services
| 文件 | 职责 |
|------|------|
| `nexus_backend/app/services/vmd_report_service.py` | VMD 报表生成服务 |

### Agent Tools
| 文件 | 职责 |
|------|------|
| `nexus_backend/app/tools/vmd_content_tools.py` | VMD 内容生成工具 |
| `nexus_backend/app/tools/vmd_tender_tools.py` | VMD 招投标工具 |
| `nexus_backend/app/tools/vmd_sales_tools.py` | VMD 销售管理工具 |
| `nexus_backend/app/tools/vmd_operation_tools.py` | VMD 运营管理工具 |
| `nexus_backend/app/tools/vmd_synergy_tools.py` | VMD 协同工具 |

## 2. FastAPI Sub-Application 挂载方案

### 目标架构

```
main_app (FastAPI)
├── /api/...          # 核心 API（auth, chat, crm 等）
└── /vmd              # VMD 子应用 (app.mount)
    ├── /tasks        # 任务管理
    ├── /clues        # 线索管理
    ├── /dashboard    # 数据看板
    └── /compliance   # 合规检查
```

### 实现方式

```python
# nexus_backend/app/vmd/__init__.py
from fastapi import FastAPI

vmd_app = FastAPI(
    title="VMD Sub-Application",
    description="Visual Merchandising & Display management module",
)

# 注册 VMD 路由
from app.vmd.routers import tasks, clues, dashboard, compliance

vmd_app.include_router(tasks.router)
vmd_app.include_router(clues.router)
vmd_app.include_router(dashboard.router)
vmd_app.include_router(compliance.router)
```

```python
# nexus_backend/app/main.py (修改)
from app.vmd import vmd_app

app.mount("/vmd", vmd_app)
```

### 路由前缀调整

当前 VMD router 使用 `/api/vmd/...` 前缀。挂载为子应用后：
- 子应用内部路由去掉 `/api/vmd` 前缀
- 通过 `app.mount("/api/vmd", vmd_app)` 保持 URL 不变
- 或使用 nginx/API Gateway 层做路由映射

## 3. 共享依赖处理方式

### 3.1 认证中间件 (Auth Middleware)

**方案：中间件复用**

```python
# app/core/auth.py 保持不变，作为共享模块

# VMD 子应用中引用同一个依赖
from app.core.auth import get_current_user_id, require_permission

vmd_app.add_middleware(AuthMiddleware)  # 或在每个路由中使用 Depends
```

**关键点：**
- `get_current_user_id` 已经是无状态的 JWT 解析，天然支持跨应用复用
- 如果未来独立部署，只需确保 JWT 签名密钥一致

### 3.2 数据库客户端 (DB Client)

**方案：共享 Supabase 客户端实例**

```python
# app/core/database.py 作为共享基础设施
# VMD 子应用直接 import
from app.core.database import supabase
```

**独立部署时的变化：**
- VMD 子应用自带 `database.py`，连接同一个 Supabase 实例
- 或使用环境变量指向独立的 DB 实例（读写分离场景）

### 3.3 事件总线 (Event Bus)

```python
# 当前：进程内事件总线
from app.services.event_bus import emit, EventType

# 独立部署后：替换为消息队列
# Redis Pub/Sub 或 RabbitMQ 作为跨进程事件传递
```

### 3.4 共享依赖汇总

| 依赖 | 当前方式 | 独立部署方式 |
|------|---------|-------------|
| Auth | 直接 import | JWT 共享密钥 |
| Database | 共享客户端 | 独立客户端连同一 DB |
| Event Bus | 进程内 emit | Redis Pub/Sub |
| Config | 共享 settings | 独立 .env |
| Cache (Redis) | 共享连接 | 共享 Redis 集群 |

## 4. 独立部署的可能性和通信方案

### 4.1 部署模式

#### 模式 A：单进程子应用（推荐近期）

```
Docker Container
└── uvicorn main:app
    ├── Core API
    └── VMD Sub-App (mounted)
```

- 优点：零通信开销，事务一致性，部署简单
- 缺点：不能独立扩缩容

#### 模式 B：独立微服务（推荐远期）

```
Container 1: Core API (port 8000)
Container 2: VMD Service (port 8001)
API Gateway (nginx/Traefik)
├── /api/vmd/* → Container 2
└── /api/*     → Container 1
```

- 优点：独立扩缩容，故障隔离
- 缺点：网络开销，分布式事务复杂

### 4.2 服务间通信

| 场景 | 方案 | 说明 |
|------|------|------|
| 同步调用 | HTTP REST | VMD 调用 Core API 获取用户信息 |
| 异步事件 | Redis Pub/Sub | 任务状态变更通知 |
| 数据共享 | 共享 PostgreSQL | 同一 Supabase 项目 |
| 文件共享 | Supabase Storage | 共享 bucket |

### 4.3 API Gateway 配置示例

```nginx
upstream core_api {
    server core:8000;
}

upstream vmd_api {
    server vmd:8001;
}

server {
    location /api/vmd/ {
        proxy_pass http://vmd_api/;
    }

    location /api/ {
        proxy_pass http://core_api/;
    }
}
```

## 5. 迁移步骤

### Phase 1：目录重组（1-2 天）

1. 创建 `nexus_backend/app/vmd/` 目录结构：
   ```
   app/vmd/
   ├── __init__.py          # FastAPI sub-app 定义
   ├── routers/
   │   ├── __init__.py
   │   ├── tasks.py         # 从 app/routers/vmd_tasks.py 移入
   │   ├── clues.py         # 从 app/routers/vmd_clues.py 移入
   │   ├── dashboard.py     # 从 app/routers/vmd_dashboard.py 移入
   │   └── compliance.py    # 从 app/routers/vmd_compliance.py 移入
   ├── services/
   │   ├── __init__.py
   │   └── report_service.py  # 从 app/services/vmd_report_service.py 移入
   └── tools/
       ├── __init__.py
       ├── content_tools.py   # 从 app/tools/vmd_content_tools.py 移入
       ├── tender_tools.py    # 从 app/tools/vmd_tender_tools.py 移入
       ├── sales_tools.py     # 从 app/tools/vmd_sales_tools.py 移入
       ├── operation_tools.py # 从 app/tools/vmd_operation_tools.py 移入
       └── synergy_tools.py   # 从 app/tools/vmd_synergy_tools.py 移入
   ```

2. 在原文件位置保留 re-export shim（兼容现有 import）

3. 运行全部测试确保无破坏

### Phase 2：子应用挂载（0.5 天）

1. 在 `app/vmd/__init__.py` 中创建 `vmd_app = FastAPI(...)`
2. 注册所有 VMD router
3. 在 `main.py` 中 `app.mount("/api/vmd", vmd_app)`
4. 移除 main.py 中对 `vmd_*` router 的直接 include
5. 验证所有 VMD 端点 URL 不变

### Phase 3：中间件迁移（0.5 天）

1. 为 VMD 子应用配置独立的中间件栈
2. 确保 auth、CORS、error handling 正确传递
3. 添加 VMD 专属的 request logging

### Phase 4：CI/CD 调整（1 天）

1. 添加 VMD 模块的独立测试 target
2. 可选：为 VMD 模块创建独立 Dockerfile
3. 更新 docker-compose 支持多容器部署

### Phase 5：独立部署准备（远期）

1. 为 VMD 模块添加独立的 `main.py` 入口
2. 配置独立的环境变量
3. 实现基于 Redis Pub/Sub 的跨服务事件
4. 添加健康检查端点
5. 配置 API Gateway 路由规则

## 6. 风险与注意事项

1. **数据库迁移**：VMD 表的 migration 仍需在主项目中管理，避免 schema 不同步
2. **Agent 工具注册**：VMD tools 需要在 Agent 启动时注册，独立部署后需通过 RPC 或 HTTP 暴露
3. **Schema 漂移**：参考 MEMORY.md 中的教训，使用 `select("*")` + Python 端兜底
4. **WebSocket**：VMD 相关的实时通知目前走主 WebSocket，独立部署后需要独立 WS 连接或消息队列

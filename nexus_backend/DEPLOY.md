# Nexus AI Command 后端部署

生产上线总清单见 `../docs/PRODUCTION_LAUNCH_CHECKLIST.md`，运行维护见 `../docs/RUNBOOK_SMALL_COMPANY.md`。本文件只说明后端构建和进程启动，避免与仓库级文档重复。

## 部署形态

| 构建上下文 | Dockerfile | 适用场景 |
|---|---|---|
| 仓库根目录 | `Dockerfile` | Zeabur 等从整个仓库构建的 PaaS |
| `nexus_backend` | `nexus_backend/Dockerfile` | 独立后端服务或本地镜像 |

两份镜像都在构建阶段安装锁定的 `requirements.txt`，运行时以非 root 用户启动 FastAPI。不要在容器启动命令中执行 `pip install`。

## 必需配置

- `ENV=production`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_JWT_SECRET` 或受支持的 JWT/JWKS 配置
- `OPENAI_API_KEY`
- `AI_BASE_URL`，目标网关必须提供 `deepseek-v4-flash`
- `REDIS_URL`、`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`
- `LANGGRAPH_CHECKPOINTER=postgres`
- `ENCRYPTION_KEY`
- `HEALTH_CHECK_TOKEN`，至少 24 个字符
- 精确的 `CORS_ORIGINS`/`ADDITIONAL_ALLOWED_ORIGINS`

完整模板见 `.env.example` 和仓库根 `.env.production.example`。聊天模型由 `app/core/config.py` 强制为 `deepseek-v4-flash`，其他环境覆盖会被忽略并记录警告。

## 数据库迁移

唯一迁移来源是仓库根 `supabase/migrations`。常规托管部署应在构建镜像之外，通过部署流水线或 Supabase CLI 按文件名顺序执行；不要使用已废弃的 `nexus_backend/supabase_migrations` 路径，也不要依赖运行镜像自动发现根目录迁移。

部署前至少运行：

```bash
python scripts/check_migration_governance.py
python scripts/scan_migration_schema_conflicts.py
python scripts/scan_rls_coverage.py
python scripts/scan_rls_policy_columns.py
python scripts/audit_schema_convergence.py
```

`AUTO_MIGRATE=true` 仅适用于明确受控且包含完整仓库迁移目录的私有部署。

## 进程

Web：

```bash
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

Worker：

```bash
celery -A app.core.celery_app.celery_app worker --loglevel=INFO --concurrency=4
```

Beat：

```bash
celery -A app.core.celery_app.celery_app beat --loglevel=INFO
```

生产必须只有一个逻辑 Beat，并使用分布式锁。知识入库、精品成果和外部集成长任务都依赖 Worker；只部署 Web 会造成页面可打开但任务长期不完成。

## 构建与验证

从仓库根目录：

```bash
docker build -t nexus-backend .
docker run --rm -p 8000:8000 --env-file .env.production nexus-backend
```

从后端目录：

```bash
cd nexus_backend
docker build -t nexus-backend .
```

部署后检查：

- `GET /health`
- `GET /health/deep` 并发送 `X-Health-Token`
- 管理员 `GET /api/system/deployment-health`
- 登录、租户隔离、SSE、企业资料入库和成果生成/下载黄金路径

如果构建日志显示 `Network is unreachable` 后又显示 `No matching distribution found`，首要问题是包索引网络不可达；检查 PaaS 出网和 `PIP_INDEX_URL`，不要先随意降低依赖版本。

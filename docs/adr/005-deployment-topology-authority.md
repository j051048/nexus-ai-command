# ADR 005：部署拓扑权威边界

- 状态：已接受
- 日期：2026-09-21
- 关联：`vercel.json`、`zeabur.yaml`、`docker-compose.yml`、`k8s/`、`scripts/check_deployment_topology.py`

## 背景

仓库同时存在四套部署描述。它们各自能跑通，但边界没有写下来，导致三个具体问题：

1. 生产后端的对外地址被写死在 `vercel.json` 的 rewrite 里，PR 预览与 staging 一旦漏配
   `VITE_API_BASE_URL` 就会继承该 rewrite，带着非生产凭据访问生产数据。
2. `k8s/*-deployment.yaml` 使用 `:latest` 浮动标签，滚动更新与回滚无法对应到不可变产物。
3. 没人能回答“客户私有化部署应该用哪一套”，运维动作依赖口头传承。

## 决策

| 面 | 权威用途 | 唯一来源 | 是否可用于生产 |
|---|---|---|---|
| Vercel（`vercel.json`） | 前端静态站点：生产与 PR 预览 | `.github/workflows/ci.yml`、`preview.yml` | 是（仅前端） |
| docker-compose（`docker-compose.yml`） | 单机自托管：后端、Celery worker、Celery beat、Redis | 根 `Dockerfile` | 是 |
| k8s（`k8s/`） | 集群化私有化部署 | 根 `Dockerfile` 构建的镜像 | 是 |
| zeabur（`zeabur.yaml`） | 内部演示与 staging 便利通道 | 根 `Dockerfile` 或构建命令 | 否（不承载生产流量） |

补充规则：

- 后端镜像只有一个构建定义（根 `Dockerfile`）；`k8s` 与 compose 都必须引用它。
- 镜像一律以显式版本标签或 digest 部署，由 `k8s/kustomization.yaml` 的 `images:` 统一改写。
- 生产后端地址只能通过 `VITE_API_BASE_URL` 注入；`vercel.json` 中的生产 rewrite 属于
  同一生产域，非生产环境必须显式覆盖，`src/lib/apiConfig.ts` 会在缺失时直接抛错。
- 新增或替换部署面必须同时更新本 ADR 与 `scripts/check_deployment_topology.py`。

## 环境矩阵

| 环境 | 前端 | 后端 | API 基址来源 |
|---|---|---|---|
| 本地开发 | Vite dev server | `uvicorn` | `VITE_API_BASE_URL=http://localhost:8000` |
| PR 预览 | Vercel preview | staging 后端 | `secrets.STAGING_API_URL`，缺失即失败 |
| staging | Vercel | staging 后端 | `secrets.STAGING_API_URL` |
| 生产 | Vercel production | 生产后端 | 生产域 rewrite（`VITE_API_BASE_URL` 可覆盖） |
| 私有化 | 客户自托管静态站点 | compose 或 k8s | 客户域名 |

## 后果

- 回滚以镜像 digest 为准，可以精确回答“上一版是什么”。
- 预览环境不可能再把写请求打到生产；缺配置时表现为构建/运行显式报错。
- 代价是新增部署面必须同步 ADR 与门禁脚本，属于有意保留的摩擦。

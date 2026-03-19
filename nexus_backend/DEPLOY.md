# Nexus AI Command — 完整部署指南

本指南覆盖从零开始部署整个 Nexus AI Command 平台的所有步骤。

---

## 架构总览

```
用户浏览器 → Vercel (前端 React SPA)
                ↓ /api/* 代理
            Zeabur / Docker (FastAPI 后端)
                ↓
        ┌───────┼───────┐
   Supabase   Redis   OpenAI 兼容 API
  (PG+Auth)  (缓存)   (AI 服务)
```

---

## 1. 外部服务准备

### 1.1 Supabase（数据库 + 认证）[必需]

1. 注册 [Supabase](https://supabase.com/) 并创建项目
2. 记录以下信息（在 Project Settings → API 中获取）：
   - `Project URL` → 用于 `SUPABASE_URL`
   - `anon/public key` → 用于前端 `VITE_SUPABASE_PUBLISHABLE_KEY`
   - `service_role key` → 用于后端 `SUPABASE_SERVICE_KEY`（⚠️ 不要暴露给前端）
   - `JWT Secret`（在 Project Settings → API → JWT Settings）→ 用于 `SUPABASE_JWT_SECRET`
   - `Project ID`（URL 中的子域名部分）→ 用于前端 `VITE_SUPABASE_PROJECT_ID`

### 1.2 AI API [必需]

系统支持任何 OpenAI 兼容 API，包括：
- OpenAI 官方: `https://api.openai.com/v1`
- 第三方中转（如 APIYi）: `https://api.apiyi.com/v1`
- 本地模型（如 Ollama）: `http://localhost:11434/v1`

需要准备：
- `OPENAI_API_KEY` — API 密钥
- `AI_BASE_URL` — API 基础地址

推荐同时配置备用 AI 服务（`AI_FALLBACK_*`），主服务欠费/故障时自动切换。

### 1.3 Redis [推荐]

用于分布式缓存、API 限流、Celery 任务队列、WebSocket PubSub。

- 单实例部署可不配置（使用内存缓存）
- 多实例/生产环境必须配置
- Zeabur 内置 Redis 服务，一键添加即可
- 或使用 [Upstash](https://upstash.com/)（免费额度）

### 1.4 APISpace 招投标数据 [可选]

用于标书审阅、招投标信息搜索功能。

1. 注册 [APISpace](https://www.apispace.com/)
2. 购买「招投标数据」API 服务
3. 获取 Token → 配置为 `APISPACE_BIDDING_TOKEN`

### 1.5 Brave Search [可选]

用于 Agent 联网搜索能力。

1. 注册 [Brave Search API](https://brave.com/search/api/)
2. 获取 API Key → 配置为 `BRAVE_SEARCH_API_KEY`

### 1.6 Sentry [可选]

前后端错误监控。

1. 注册 [Sentry](https://sentry.io/)
2. 创建项目，获取 DSN
3. 后端: `SENTRY_DSN`，前端: `VITE_SENTRY_DSN`

### 1.7 Langfuse [可选]

LLM 调用链路追踪，用于监控 AI 质量和成本。

1. 注册 [Langfuse](https://langfuse.com/)
2. 创建项目，获取 Public Key / Secret Key
3. 配置 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_HOST`

### 1.8 通知渠道 [可选]

按需配置企业微信/钉钉/飞书 Webhook，用于审批通知、超时提醒等。详见 `.env.example` 中对应配置段。

### 1.9 支付 [可选]

按需配置 Stripe（国际）/ 微信支付 / 支付宝。详见 `.env.example` 中对应配置段。

---

## 2. 数据库初始化

在 Supabase SQL Editor 中按顺序运行迁移文件：

```bash
# 迁移文件位于
nexus_backend/supabase_migrations/migrations/

# 共 78 个迁移文件，必须按文件名时间戳顺序执行
# 第一个: 20240126000000_initial_schema.sql（创建所有基础表）
# 最后一个: 20260319_memory_pattern_key_and_failure_pattern.sql
```

执行步骤：
1. 打开 Supabase Dashboard → SQL Editor
2. 按文件名排序，依次复制粘贴每个 `.sql` 文件内容并执行
3. 首次部署建议运行 `20240126999999_seed_data.sql` 填充示例数据

> 提示：文件名前缀即为执行顺序，如 `20240126` 在 `20240127` 之前。

---

## 3. 后端部署

### 方式 A: Zeabur 部署（推荐）

1. 登录 [Zeabur](https://zeabur.com/)，创建新项目
2. 添加服务 → 从 GitHub 仓库部署（选择 `nexus_backend` 目录）
3. 添加 Redis 服务（Zeabur 内置，一键添加）
4. 在服务设置中配置环境变量（参考 `nexus_backend/.env.example`）：

**最小必需变量：**
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJxxx...
SUPABASE_JWT_SECRET=your-jwt-secret
OPENAI_API_KEY=sk-xxx
AI_BASE_URL=https://api.openai.com/v1
REDIS_URL=redis://xxx  (Zeabur 自动注入)
ENV=production
```

5. 等待构建完成，获得 `https://xxx.zeabur.app` 访问地址
6. 验证: 访问 `https://xxx.zeabur.app/docs` 查看 API 文档

### 方式 B: Docker 部署

```bash
cd nexus_backend

# 构建镜像
docker build -t nexus-backend .

# 运行（传入环境变量）
docker run -d \
  --name nexus-backend \
  -p 8000:8000 \
  --env-file .env \
  nexus-backend
```

Docker 镜像特性：
- 基于 `python:3.11-slim`，多阶段构建
- 内置 `ffmpeg`（音频转码支持）
- 非 root 用户运行
- 内置健康检查: `GET /health`

### Celery Worker（定时任务）

如需定时任务功能（用户自定义定时任务、审批超时提醒等），需额外启动 Celery：

```bash
# Worker
celery -A app.tasks.celery_app worker --loglevel=info

# Beat（定时调度器）
celery -A app.tasks.celery_app beat --loglevel=info
```

> 需要 Redis 作为 Broker，确保 `CELERY_BROKER_URL` 已配置。

---

## 4. 前端部署

### 方式 A: Vercel 部署（推荐）

1. 在 [Vercel](https://vercel.com/) 导入 GitHub 仓库
2. Framework Preset 选择 `Vite`
3. Root Directory 保持默认（项目根目录）
4. 配置环境变量：

```
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=eyJxxx...
VITE_SUPABASE_PROJECT_ID=your-project-id
VITE_API_BASE_URL=https://your-backend.zeabur.app
```

5. 部署完成后，`vercel.json` 会自动将 `/api/*` 请求代理到后端

> 注意：`vercel.json` 中的后端地址需要与实际后端地址一致，当前配置为 `https://aizhz.zeabur.app`。如果你的后端地址不同，需要修改 `vercel.json`。

### 方式 B: 本地构建 + 静态托管

```bash
# 安装依赖
npm install

# 构建
npm run build

# 产物在 dist/ 目录，部署到任意静态托管服务
```

### 本地开发

```bash
# 创建环境变量
cp .env.example .env
# 编辑 .env 填入实际值

npm install
npm run dev
# 访问 http://localhost:5173
```

---

## 5. CI/CD 配置

项目使用 GitHub Actions，需要在仓库 Settings → Secrets and variables → Actions 中配置：

### 必需 Secrets

| Secret | 说明 |
|--------|------|
| `VITE_SUPABASE_URL` | Supabase 项目 URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Supabase anon key |
| `SUPABASE_URL` | 同上（后端测试用） |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `OPENAI_API_KEY` | AI API Key（后端测试用） |

### Vercel 部署 Secrets

| Secret | 说明 |
|--------|------|
| `VERCEL_TOKEN` | Vercel API Token |
| `VERCEL_ORG_ID` | Vercel 组织 ID |
| `VERCEL_PROJECT_ID` | Vercel 项目 ID |

### 后端部署 Secrets

| Secret | 说明 |
|--------|------|
| `DEPLOY_WEBHOOK_URL` | 生产环境部署 Webhook（Zeabur） |
| `STAGING_DEPLOY_WEBHOOK_URL` | Staging 环境部署 Webhook |
| `DOCKER_REGISTRY` | Docker 镜像仓库地址（Docker 部署时） |
| `DOCKER_USERNAME` | Docker 仓库用户名 |
| `DOCKER_PASSWORD` | Docker 仓库密码 |

### Staging 环境 Secrets（可选）

| Secret | 说明 |
|--------|------|
| `STAGING_SUPABASE_URL` | Staging Supabase URL |
| `STAGING_SUPABASE_PUBLISHABLE_KEY` | Staging Supabase anon key |

### CI 流水线说明

- `ci.yml` — 主流水线：前端 lint/test/typecheck/build + 后端 lint/test + 安全扫描 + E2E + 部署
- `test.yml` — 集成测试门禁：pytest + vitest + 覆盖率上报 Codecov
- `preview.yml` — PR 预览环境：自动部署 Vercel preview + PR 评论预览 URL

---

## 6. 本地开发（全栈）

```bash
# 1. 克隆项目
git clone https://github.com/j051048/nexus-ai-command.git
cd nexus-ai-command

# 2. 后端
cd nexus_backend
cp .env.example .env
# 编辑 .env 填入 Supabase + AI API 配置
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. 前端（新终端）
cd ..
cp .env.example .env
# 编辑 .env，设置 VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev

# 4. 访问 http://localhost:5173
```

---

## 7. 验证清单

部署完成后，逐项验证：

- [ ] 后端健康检查: `GET /health` 返回 200
- [ ] API 文档可访问: `GET /docs`
- [ ] 前端页面正常加载，无白屏
- [ ] 用户注册/登录正常（Supabase Auth）
- [ ] AI 对话正常响应（测试发送一条消息）
- [ ] 前端 → 后端 API 代理正常（无 CORS 错误）

---

## 8. 常见问题

**Q: 前端请求后端报 CORS 错误？**
A: 检查后端 `ADDITIONAL_ALLOWED_ORIGINS` 是否包含前端域名。Vercel 部署时通过 `vercel.json` 代理，不应有 CORS 问题。

**Q: AI 对话无响应？**
A: 检查 `OPENAI_API_KEY` 和 `AI_BASE_URL` 是否正确，确认 API 余额充足。查看后端日志排查。

**Q: 定时任务不执行？**
A: 需要单独启动 Celery Worker + Beat，且 Redis 必须可用。

**Q: 数据库迁移报错？**
A: 确保按文件名顺序执行。如果中途失败，修复后从失败的文件重新执行即可。

# Nexus AI Command

> AI 驱动的企业智能管理平台 — 对话即操作，AI 即中枢

Nexus AI Command 是一个全功能企业级 AI 管理平台，覆盖销售、CRM、审批、OA、HR、财务、合同、资产、库存、工单、知识库等核心业务场景。系统以 AI 对话为核心交互方式，所有操作均可通过自然语言与 AI 助手协作完成。

---

## 核心特性

- **AI-First 交互**: LangGraph 多 Agent 编排，4 级复杂度智能路由，支持 WBS 任务分解
- **100+ AI 工具**: 覆盖 CRM、OA、财务、HR、审批、合同、资产、库存、工单、证照、竞品分析等
- **多租户隔离**: 组织级数据隔离，Supabase RLS 行级安全策略
- **可视化工作流**: 基于 React Flow 的拖拽式审批流程设计器
- **VMD 营销数字化**: 内容生成、投标文档、销售赋能、竞品分析、私域运营
- **企业级安全**: CSRF 防护、CSP Nonce、HSTS、API Rate Limiting、数据脱敏
- **PWA 支持**: 离线可用，支持安装为桌面/移动应用

---

## 技术架构

```
┌──────────────────────────────────────────────────────────┐
│  前端 (React + Vite + TypeScript + TailwindCSS)          │
│  Radix UI + React Flow + TanStack Query + Sentry         │
├──────────────────────────────────────────────────────────┤
│  后端 (FastAPI + LangGraph + Celery)                     │
│  61 路由 · 90+ 服务 · 100+ AI 工具                       │
├──────────────────────────────────────────────────────────┤
│  数据层 (Supabase + PostgreSQL + pgvector + Redis)       │
│  RLS 多租户 · 向量检索 · 语义缓存 · EventBus             │
├──────────────────────────────────────────────────────────┤
│  AI 引擎 (OpenAI 兼容 API)                               │
│  GPT · Claude · Gemini · 本地模型 · 任意兼容服务          │
└──────────────────────────────────────────────────────────┘
```

### Agent 架构

```
用户输入 → 意图路由(4级复杂度) → Plan → Execute(工具调用) → Reflect(幻觉检测) → Critic → Respond
                                   ↑        ↓
                                   └── 循环 ──┘

复杂任务 → WBS 分解 → 多子任务并行编排 → 整合响应
```

关键机制: 工具执行超时(30s/120s)、结果截断(2000字符)、循环检测(MD5指纹)、HITL 确认门控、断路器、幂等性缓存。

---

## 功能模块

| 模块 | 说明 | 角色 |
|------|------|------|
| 战绩中心 | 个人销售仪表板、绩效评分、排行榜 | 所有人 |
| 总控中心 | 企业全局管控、AI 周报、异常队列 | Boss |
| CRM 客户管理 | 客户 CRUD、跟进记录、销售漏斗、阶段推进 | 所有人 |
| 智能审批 | AI 辅助审批、批量处理、异常检测 | 所有人 |
| 工作流设计器 | 可视化审批流程设计、模板市场 | Boss |
| 项目管理 | AI 创建项目、任务分解、进度跟踪 | 所有人 |
| 合同管理 | 合同全生命周期、AI 分析、到期提醒 | Manager+ |
| OA 办公 | 请假、会议、任务、交接、入职 | 所有人 |
| 人事中心 | 考勤、排班、薪资、绩效、招聘 | Manager+ |
| 财务中心 | 报销、预算、发票 OCR、计费 | 所有人 |
| 资产管理 | 资产全生命周期、调拨、统计 | 所有人 |
| 库存管理 | 出入库、库存统计 | 所有人 |
| 工单系统 | 工单创建/分配/跟踪 | 所有人 |
| 证照管理 | 证照到期预警、续期管理 | 所有人 |
| 知识库 | 文档上传、AI 解析、向量检索 | 所有人 |
| VMD 营销中心 | 内容生成、投标、竞品分析、私域运营 | 所有人 |
| 数据报表 | 销售/审批/绩效/使用报表 | 所有人 |
| 标书审阅 | AI 招标文件分析、风险评估 | 所有人 |
| 竞品库 | Battlecard、竞品对比、应对话术 | 所有人 |
| 培训中心 | 课程、测验、成就系统 | 所有人 |
| 激励钱包 | 奖金记录、成就徽章 | 所有人 |
| 插件市场 | 功能扩展插件安装/管理 | Boss |
| 定时任务 | 用户自定义 AI 定时任务 | 所有人 |

---

## 快速开始

### 前置条件

- Node.js 20+
- Python 3.11+
- Supabase 项目 (免费版即可)
- OpenAI 兼容 API Key
- Redis (可选，用于分布式缓存)

### 1. 克隆项目

```bash
git clone <YOUR_GIT_URL>
cd nexus-ai-command
```

### 2. 后端启动

```bash
cd nexus_backend
cp .env.example .env
# 编辑 .env 填写 Supabase 和 AI API 配置

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

后端 API 文档: `http://localhost:8000/docs`

### 3. 前端启动

```bash
cd nexus_frontend
npm install
# 创建 .env 文件，配置 VITE_API_BASE_URL 和 VITE_SUPABASE_URL

npm run dev
```

前端访问: `http://localhost:5173`

### 4. 数据库初始化

在 Supabase SQL Editor 中依次运行 `nexus_backend/supabase_migrations/` 下的迁移文件。详见 [部署指南](nexus_backend/DEPLOY.md)。

---

## 目录结构

```
nexus-ai-command/
├── nexus_frontend/          # React 前端
│   ├── src/
│   │   ├── components/      # UI 组件
│   │   ├── pages/           # 48 个页面
│   │   ├── hooks/           # 自定义 Hooks
│   │   └── lib/             # 工具函数
│   └── public/              # 静态资源 + PWA
├── nexus_backend/           # FastAPI 后端
│   ├── app/
│   │   ├── agent/           # LangGraph Agent 编排
│   │   ├── routers/         # 61 个 API 路由
│   │   ├── services/        # 90+ 业务服务
│   │   ├── tools/           # 100+ AI 工具
│   │   ├── core/            # 安全、认证、数据库
│   │   └── tasks/           # Celery 定时任务 + 事件传感器
│   ├── supabase_migrations/ # 数据库迁移 SQL
│   └── Dockerfile           # 生产部署
├── docs/                    # 项目文档
│   ├── USER_GUIDE.md        # 系统使用说明书
│   ├── AI_FIRST_ENTERPRISE_DESIGN.md
│   ├── DISASTER_RECOVERY.md
│   ├── ROLLBACK.md
│   └── adr/                 # 架构决策记录
└── .github/workflows/       # CI/CD (GitHub Actions)
```

---

## 部署

| 组件 | 推荐方案 | 文档 |
|------|---------|------|
| 前端 | Vercel | CI/CD 自动部署 |
| 后端 | Zeabur / Docker | [DEPLOY.md](nexus_backend/DEPLOY.md) |
| 数据库 | Supabase Cloud | [DEPLOY.md](nexus_backend/DEPLOY.md) |
| 缓存 | Redis (Zeabur 内置) | .env 配置 |

灾难恢复: [DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md) | 回滚手册: [ROLLBACK.md](docs/ROLLBACK.md)

---

## 文档

- [系统使用说明书](docs/USER_GUIDE.md) — 完整功能操作指南
- [AI-First 设计方案](docs/AI_FIRST_ENTERPRISE_DESIGN.md) — 产品设计理念与架构
- [实施指南](docs/AI_FIRST_IMPLEMENTATION_GUIDE.md) — 开发实施步骤
- [三级权限系统](docs/three-tier-permission-system.md) — Boss / Manager / Employee 权限设计
- [架构决策记录](docs/adr/) — 技术选型决策（Supabase、LangGraph、单例模式）
- [部署指南](nexus_backend/DEPLOY.md) — Supabase + Zeabur 部署

---

## 环境变量

关键配置项（完整列表见 `nexus_backend/.env.example`）:

| 变量 | 说明 | 必填 |
|------|------|:----:|
| `SUPABASE_URL` | Supabase 项目 URL | Yes |
| `SUPABASE_SERVICE_KEY` | Supabase Service Role Key | Yes |
| `OPENAI_API_KEY` | AI API Key (全局默认) | Yes |
| `AI_BASE_URL` | AI API 地址 | Yes |
| `REDIS_URL` | Redis 连接地址 | No |
| `SENTRY_DSN` | Sentry 错误监控 | No |
| `RATE_LIMIT_PER_MINUTE` | API 限流 (默认 60) | No |
| `MAX_TOKENS_PER_DAY` | 每日 Token 上限 (默认 1M) | No |

---

## 许可证

私有项目，未经授权不得分发。

# Nexus AI Command

Nexus AI Command 是面向科学仪器生产、销售与服务企业的 AI 作战系统。当前商业主线聚焦虚拟市场部（VMD）、CRM、投标与知识助手；OA、HR、财务等横向能力作为可选企业模块维护。

## 核心能力

- **AI 作战闭环**：线索发现、客户跟进、竞品战卡、投标分析和经营复盘。
- **Agent 编排**：LangGraph 路由、规划、执行、反思、审查与响应，包含 HITL、工具 RBAC、熔断和补偿。
- **企业知识与记忆**：文档检索、业务关系图谱、来源追踪、记忆生命周期与用户可控遗忘。
- **多租户底盘**：Supabase/PostgreSQL、RLS、组织上下文、审计日志和权限边界。
- **成本治理**：聊天模型由后端统一强制为 `deepseek-v4-flash`，模型升级必须通过成本策略门禁。

## 技术栈

| 层 | 技术 |
|---|---|
| Web | React 18、TypeScript、Vite、TanStack Query、Radix UI |
| API | FastAPI、Pydantic、PostgREST/Supabase |
| Agent | LangGraph、结构化工具目录、SSE |
| 异步任务 | Celery、Redis、分布式锁 |
| 数据 | PostgreSQL、pgvector、Supabase RLS |
| 质量 | Vitest、Playwright、pytest、Ruff、Black、mypy、静态治理脚本 |

实时工程规模见[自动生成的事实清单](docs/handbook/generated/inventory.md)，不要在文档中手写容易过期的文件或迁移数量。

## 本地启动

前置环境：Node.js 20+、Python 3.11、PostgreSQL/Supabase，以及可选的 Redis。

```bash
# 前端
npm ci
cp .env.example .env
npm run dev

# 后端（另一个终端）
cd nexus_backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Windows
cp .env.example .env
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

Linux/macOS 请将 `.venv/Scripts/...` 替换为 `.venv/bin/...`。环境变量说明以根目录和 `nexus_backend/.env.example` 为准，不要提交真实密钥。

## 常用质量命令

```bash
npx tsc --noEmit
npm run lint
npm test
npm run build
node scripts/check_source_size.mjs

cd nexus_backend
ruff check app/
black --check app/
pytest tests/unit -q
```

交接与发布门禁：

```bash
python scripts/generate_handover_inventory.py --check
python scripts/check_handover_readiness.py
python scripts/check_exception_governance.py
python scripts/production_proof_gate.py
```

## 阅读顺序

1. [工程接管入口](docs/handbook/00-start-here.md)
2. [架构总览](docs/architecture.md)
3. [系统边界](docs/handbook/01-system-map.md)
4. [本地开发](docs/handbook/02-local-development.md)
5. [Agent 生命周期](docs/handbook/05-agent-lifecycle.md)
6. [测试与发布](docs/handbook/07-testing-and-release.md)
7. [已知债务](docs/handbook/09-known-debt.md)

## 贡献与安全

- 开发流程与 PR 约束见 [CONTRIBUTING.md](CONTRIBUTING.md)。
- 安全问题处理见 [SECURITY.md](SECURITY.md)。
- 生产部署前执行 [上线检查表](docs/PRODUCTION_LAUNCH_CHECKLIST.md)。
- 小团队值守流程见 [运行手册](docs/RUNBOOK_SMALL_COMPANY.md)。

本仓库仍包含大量渐进治理中的历史模块。新增能力必须遵循现有领域边界、租户隔离、工具风险声明和测试门禁，禁止以一次性大重写替代可回滚的增量演进。

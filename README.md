# Nexus AI Command

Nexus AI Command 是面向科学仪器生产、销售、研发与服务企业的 AI 增长与成果交付系统，重点服务光谱、色谱、质谱、能谱和电子仪器产品线。产品主线不是堆叠通用 SaaS 页面，而是把企业资料、客户机会、方案/投标作战和可下载成果连成一个可审计闭环；OA、HR、财务等横向能力按客户需要启用或连接现有系统。

## 核心能力

- **AI 增长闭环**：线索发现、客户跟进、竞品战卡、方案作战、投标作战和经营复盘。
- **Agent 编排**：LangGraph 路由、规划、执行、反思、审查与响应，包含 HITL、工具 RBAC、熔断和补偿。
- **企业知识底座**：产品资料、仪器手册、案例、竞品、法规和历史方案统一入库，支持混合检索、来源追踪、质量审核与关系洞察。
- **精品成果交付**：基于已选企业证据深度生成客户方案、标书、报告和表格，经结构与语义质量门后持久化输出 Word、PDF 或 Excel，并在成果中心持续可下载；对话内容另支持图片快速导出。
- **多租户底盘**：Supabase/PostgreSQL、RLS、组织上下文、审计日志和权限边界。
- **成本治理**：聊天模型由后端统一强制为 `deepseek-v4-flash`，模型升级必须通过成本策略门禁。

## 首次使用主线

1. 在“企业资料”上传公司介绍、产品参数、应用案例、竞品资料、法规和历史方案，等待状态变为可检索。
2. 在“客户与项目”维护客户行业、预算、地域、样品、检测目标和项目阶段。
3. 进入“方案作战”或“投标作战”，让 AI 先核验需求和证据缺口，再生成草稿。
4. 人工确认事实与外部承诺，运行质量复核后下载最终文件；所有版本会汇集到右上角“成果”入口。

普通用户只需选择业务场景并用自然语言下达任务，不需要选择模型或阅读内部推理链。管理员可在 Agent Ops、成果质量和成本看板中查看结构化证据。

## 技术栈

| 层 | 技术 |
|---|---|
| Web | React 18、TypeScript、Vite、TanStack Query、Radix UI |
| API | FastAPI、Pydantic、PostgREST/Supabase |
| Agent | LangGraph、结构化工具目录、SSE |
| 异步任务 | Celery、Redis、分布式锁 |
| 数据 | PostgreSQL、pgvector、Supabase RLS |
| 文件交付 | python-docx、ReportLab、openpyxl、持久化成果任务 |
| 质量 | Vitest、Playwright、pytest、Ruff、Black、mypy、静态治理脚本 |

实时工程规模见[自动生成的事实清单](docs/handbook/generated/inventory.md)，不要在文档中手写容易过期的文件或迁移数量。

## 本地启动

前置环境：Node.js 20+、Python 3.11、PostgreSQL/Supabase，以及可选的 Redis。

```bash
# 前端
npm ci
cp .env.example .env
npm run dev
```

后端在另一个终端启动。Windows PowerShell：

```powershell
cd nexus_backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Linux/macOS：

```bash
cd nexus_backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

环境变量说明以根目录和 `nexus_backend/.env.example` 为准，不要提交真实密钥。

## 常用质量命令

```bash
npx tsc --noEmit
npm run lint
npm test
npm run build
npm run quality:frontend

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
python scripts/customer_acceptance_gate.py
python scripts/release_quality_gate.py
python scripts/production_proof_gate.py
```

真实“上传资料 -> 入库 -> 深度生成 -> DOCX/PDF 下载”需要已部署环境和专用测试租户：

```bash
python scripts/run_customer_golden_acceptance.py --require-live
```

所需变量和静态/在线证明的区别见[客户验收标准](docs/CUSTOMER_ACCEPTANCE_CRITERIA.md)。

## 阅读顺序

1. [文档地图](docs/README.md)
2. [工程接管入口](docs/handbook/00-start-here.md)
3. [架构总览](docs/architecture.md)
4. [本地开发](docs/handbook/02-local-development.md)
5. [Agent 生命周期](docs/handbook/05-agent-lifecycle.md)
6. [文档交付质量平台](docs/DOCUMENT_QUALITY_PLATFORM.md)
7. [测试与发布](docs/handbook/07-testing-and-release.md)
8. [已知债务](docs/handbook/09-known-debt.md)

## 贡献与安全

- 开发流程与 PR 约束见 [CONTRIBUTING.md](CONTRIBUTING.md)。
- 安全问题处理见 [SECURITY.md](SECURITY.md)。
- 生产部署前执行 [上线检查表](docs/PRODUCTION_LAUNCH_CHECKLIST.md)。
- 小团队值守流程见 [运行手册](docs/RUNBOOK_SMALL_COMPANY.md)。

本仓库仍包含大量渐进治理中的历史模块。新增能力必须遵循现有领域边界、租户隔离、工具风险声明和测试门禁，禁止以一次性大重写替代可回滚的增量演进。

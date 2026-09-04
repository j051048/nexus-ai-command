# 文档交付质量平台

Nexus 的方案、标书和通用成果文件共用同一套交付内核。平台负责模板选择、证据约束、格式检查、安全扫描、语义评审、失败修复和质量留痕，避免各入口各自维护一套生成逻辑。

## 用户交付入口

- 方案工作区：`/growth/solutions`，按需求、证据、配置、撰写、复核和交付推进。
- 投标工作区：`/growth/tenders`，旧 `/tender-analysis` 入口保持兼容。
- 对话成果：消息下方“制作精品成果”会创建深度生成任务，不直接导出聊天气泡。
- 全局成果中心：桌面和移动布局均可查看状态、质量、证据、版本并再次下载。
- 管理端：`/artifact-quality` 查看一次通过率、证据覆盖、失败模式和任务健康。

## 已接入能力

### 统一质量门

`app/services/artifact_llm_judge.py` 的 `evaluate_delivery_package` 是统一入口，组合以下检查：

- 确定性规则：章节、字数、引用和证据覆盖；
- 格式检查：标题层级、表格、列表、代码围栏和空段落；
- 交付安全：PII、内部标记、不当承诺和 DOCX 渲染完整性；
- 语义评审：证据忠实度、客户价值、逻辑连贯性和语言专业度。

LLM 评审不可用时会降级为确定性结论，不会隐藏失败原因。对外交付仍受硬性门禁约束。

### 深度生成与自动修复

`app/services/artifact_generation_service.py` 已接入：

1. 企业知识检索和证据包构建；
2. 科学仪器领域结构规划；
3. 黄金模板选择与提示词注入；
4. 初稿生成、事实核验、反思和定向修复；
5. 统一质量门与最终文件渲染；
6. 模板使用效果和质量事件回写。

### 持久化异步任务

`artifact_generation_jobs` 保存任务状态、阶段、进度、输入快照、结果和失败原因。HTTP 接口支持创建、查询、取消和重试；Celery 不可用时由 FastAPI 后台任务降级执行。

任务状态：`queued -> running -> completed | failed | cancelled`。

Worker 使用租约和心跳领取任务；中断任务可恢复、取消或重试。前端轮询只负责展示状态，不承担任务执行。

### 模板和反馈闭环

- `artifact_template_service.py`：按成果类型、仪器谱系和行业选择版本化模板，并根据通过率与质量分做 A/B 排序；
- `artifact_feedback_loop.py`：记录采用、编辑、放弃、赢单和输单结果，提取人工修改差异；
- `artifact_quality_service.py`：保存模板、规则、语义评审和交付门禁快照；
- `artifact_quality_slo.py`：输出一次通过率、平均质量分、证据覆盖率和失败模式。

## 数据迁移

按顺序执行：

1. `supabase/migrations/20260806_artifact_quality_platform.sql`
2. `supabase/migrations/20260810_001_artifact_generation_jobs.sql`
3. `supabase/migrations/20260810_002_knowledge_activation.sql`
4. `supabase/migrations/20260810_003_operational_closure.sql`

这些迁移包含租户字段、索引、RLS、任务租约、入库恢复和交付事件。部署前必须通过 schema convergence 与 RLS coverage 检查。

## 运营原则

- 真实企业资料不足时明确列出缺口，不编造参数、案例或政策；
- 高风险结论必须可追溯到文档和证据片段；
- 低质量结果保留为草稿，不标记为可交付；
- 只有经人工审核的高质量样本才能进入模板或 few-shot 候选池；
- 质量、延迟和成本按组织、成果类型和模板版本留痕。

## 验证

```bash
# 静态契约与离线评测
python scripts/production_proof_gate.py
python scripts/build_artifact_eval_contract_outputs.py
python scripts/run_artifact_output_eval.py

# 浏览器交付链路
npx playwright test e2e/customer-business-acceptance.spec.ts --project=chromium
npx playwright test e2e/solution-workspace.spec.ts e2e/tender-workspace.spec.ts --project=chromium

# 已部署环境的上传、入库、深度生成与文件下载
python scripts/run_customer_golden_acceptance.py --require-live
```

最后一条必须配置 `GOLDEN_ACCEPTANCE_BASE_URL`、`GOLDEN_ACCEPTANCE_TOKEN` 和 `GOLDEN_ACCEPTANCE_ORG_ID`。无凭据的静态 skip 不代表真实交付已通过。

## 后续迭代

1. 将已审核成果沉淀为可治理的 few-shot 样本，而不是自动学习全部人工修改；
2. 扩充质量 SLO、失败模式和模板效果的真实客户基线；
3. 用真实模型输出运行 `scripts/run_artifact_output_eval.py`，形成版本化回归基线；
4. 将客户赢单、投标通过和方案采用结果纳入模板晋升门槛。

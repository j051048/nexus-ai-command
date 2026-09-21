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

- `artifact_template_service.py`：按成果类型、仪器谱系和行业选择版本化模板；A/B 排序使用通过率与质量分，并在样本 ≥ 5 时叠加客户赢单率（±10 分重排序）；`promote_template` 是草稿晋升黄金模板的门禁，要求均分 ≥ 85、通过率 ≥ 90%、客户结果样本 ≥ 5 且赢率 ≥ 50%；
- `artifact_feedback_loop.py`：记录采用、编辑、放弃、赢单和输单结果，提取人工修改差异；学习候选只有 `recorded`/`review_candidate` 两种开放态，`approved`/`rejected` 只能由管理员通过 `POST /api/artifact-quality/learning-candidates/{id}/review` 写入，且 `auto_apply` 恒为 false；
- `artifact_quality_service.py`：保存模板、规则、语义评审和交付门禁快照；
- `artifact_quality_slo.py`：输出一次通过率、平均质量分、证据覆盖率、LLM 评审四维度均值和失败模式。

客户结果回流路径：`POST /api/artifact-quality/outcomes` → 写 `artifact_feedback_events` 与 `artifact_delivery_events` → 从 `artifacts.metadata.template.template_key` 反查模板 → 折算进模板指标。因此模板的 A/B 结论同时受质量分和真实赢单结果影响。

### 人工审批与晋升门禁

| 门 | 入口 | 规则 |
|---|---|---|
| 学习候选审批 | `POST /api/artifact-quality/learning-candidates/{event_id}/review` | 仅组织管理员；只能把开放态改成 `approved`/`rejected`；记录 `reviewed_by`/`reviewed_at`/`review_note`；重复审批返回“候选不存在或已审批” |
| 模板晋升 | `POST /api/artifact-quality/templates/{template_key}/promote` | 只有组织管理员；未达标返回 422 与 `blockers`；`force=true` 可人工覆盖，但覆盖事实写入模板指标 |
| 外发阻断 | 生成管线内的 `evaluate_delivery_package` | PII、内部标记、不当承诺或 DOCX 渲染异常直接令 `ready=false` |

## 数据迁移

按顺序执行：

1. `supabase/migrations/20260806_artifact_quality_platform.sql`
2. `supabase/migrations/20260810_001_artifact_generation_jobs.sql`
3. `supabase/migrations/20260810_002_knowledge_activation.sql`
4. `supabase/migrations/20260810_003_operational_closure.sql`
5. `supabase/migrations/20260921_001_artifact_feedback_review_loop.sql`（补 `change_type`、审批审计字段，并放开未评分的编辑记录）

这些迁移包含租户字段、索引、RLS、任务租约、入库恢复和交付事件。部署前必须通过 schema convergence 与 RLS coverage 检查。

## 质量基线与回归

`nexus_backend/evals/artifact_output_baseline.json` 是版本化的产物评测基线，由 `scripts/run_artifact_output_eval.py` 写入和比对：

```bash
# 用契约夹具跑一遍（CI 默认路径）
python scripts/build_artifact_eval_contract_outputs.py --output /tmp/outputs.json
python scripts/run_artifact_output_eval.py /tmp/outputs.json --label contract-fixture

# 用真实模型录制输出后刷新基线（低于 golden 下限会被拒绝）
python scripts/run_artifact_output_eval.py recorded/live-model.json --update-baseline --label live-model
```

脚本在 `pass_rate` 下降或任何用例由通过转为失败时以 `ARTIFACT_OUTPUT_EVAL_REGRESSION` 失败。当前基线的 `source` 为 `contract-fixture`，即验证的是评测器契约而非真实模型质量；真实模型基线需在具备模型凭据的环境录制后提交，替换前不得对外声明模型回归已覆盖。

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

已完成：

- 学习候选的人工审批门与管理端入口；
- 客户赢单/输单折入模板 A/B 与晋升门槛；
- LLM 评审四维度落库并在运营看板呈现；
- 产物评测的版本化基线与 CI 回归门禁。

待办：

1. 在具备模型凭据的环境录制真实模型输出，把 `artifact_output_baseline.json` 的 `source` 从 `contract-fixture` 升级为 `live-model`；
2. 将已审核成果沉淀为可治理的 few-shot 样本，而不是自动学习全部人工修改；
3. 为黄金模板库补充按行业 × 仪器线的真实客户样本量与赢单分布报表；
4. 月度质量报告自动落库并推送，而不是只按需查询。

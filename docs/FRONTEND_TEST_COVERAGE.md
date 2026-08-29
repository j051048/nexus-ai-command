# 前端测试覆盖率:现状、门槛与路线

> 本文档回答三个问题:前端测试现在到底覆盖了什么、为什么 CI 的阈值是这样、以及如何有计划地提高覆盖率。任何对 `vitest.config.ts` 阈值或 CI 覆盖率步骤的修改都应同步更新本文档。

## 1. 现状(2026-08 基线)

从 `coverage/coverage-summary.json` 读取:

| 指标 | 当前 | 文件数 | 备注 |
|---|---:|---:|---|
| 行覆盖 | 13.1% | 2055 / 15672 | 461 个文件中有 **304 个为 0%** |
| 语句覆盖 | 12.4% | 2162 / 17453 | |
| 函数覆盖 | 9.1% | 503 / 5550 | |
| 分支覆盖 | 8.8% | 1291 / 14740 | |
| 测试规模 | 207 个测试 / 81 个套件 | | 全部通过 |

核心业务页面(`OACenter.tsx`、`LLMModelManagement.tsx`、`CustomerDetailSheet.tsx`、`HRCenter.tsx` 等)目前几乎没有任何组件级测试;已有的测试主要集中在 hooks、工具函数和少量组件(如 `ThinkingChain` 96%、`useChatPanel` 35%)。

## 2. 门槛设计(诚实的两道防线)

历史上 CI 有一个"覆盖率低于 65% 只 warning"的检查,既无法阻止回归,又制造了"有质量门禁"的错觉。现已改为两道真实防线:

### 防线一:vitest 硬阈值(vitest.config.ts)

阈值 = 当前真实基线,仅防止覆盖率继续下滑:

```ts
lines: 12.0, branches: 7.5, functions: 8.0, statements: 11.0
```

低于该值本地 `npm test -- --coverage` 直接失败。**它不是质量目标**,只是"不准更差"。

### 防线二:CI 趋势门禁(scripts/check_frontend_coverage_trend.mjs)

CI 在每次测试后将当前覆盖率与仓库基线 `docs/test-coverage/frontend-baseline.json` 比较,任一指标下降超过 0.75 个百分点即失败。基线更新方式:

```bash
npm run test -- --coverage
node scripts/check_frontend_coverage_trend.mjs --update
git add docs/test-coverage/frontend-baseline.json
```

更新基线只应在**有真实测试资产新增/改进**时进行,不允许用"更新基线"绕过一次具体回退。

## 3. 质量目标与路线

覆盖率本身不是目的,保护关键路径才是。分三个阶段:

### 阶段 A(近期,~1-2 个月):核心路径保护

- 目标:行覆盖 13% → 25%;核心页面测试矩阵建立
- 优先为以下 12 个高价值路径补组件/集成测试:
  1. 登录与会话恢复(`auth`、`session` hooks)
  2. AI 聊天主面板(`useChatPanel` 已 35%,补到 60%+)
  3. VMD 任务中心(VMDCenter 已 59%,保持并扩展)
  4. CRM 客户列表与详情
  5. 审批流(ApprovalFlow)
  6. 投标分析页
  7. 文档/知识库检索
  8. 解决方案工作区
  9. 合同管理
  10. 通知中心
  11. 工作流设计器(WorkflowDesigner 已 42%,补到 60%+)
  12. 财务中心只读视图
- 验收标准:上述页面每个至少 1 个关键交互测试,0% 文件数降到 200 以下

### 阶段 B(中期,~1 个季度):组件层系统覆盖

- 目标:行覆盖 25% → 40%
- 为 `src/components` 的通用组件(shadcn 变体、ai/genui 系列)建立 Storybook 式行为测试
- 为 `src/api`、`src/services`、`src/hooks` 的纯逻辑建立 80%+ 覆盖

### 阶段 C(长期):回归网完整化

- 目标:行覆盖 40% → 60%+(对单体前端而言 60% 已是健康的商业应用水平)
- 巨型页面先拆组件再测(拆分为可独立测试的模块是前提)
- 将 E2E 与组件测试按核心路径矩阵一一映射,形成三层防线

## 4. 不要做的事

- 不要为了覆盖率数字写"断言实现细节"的测试(如断言某个内部函数被调用);
- 不要把阈值改回低于当前基线的值而不说明理由;
- 不要用 `// istanbul ignore` 批量豁免业务代码(仅允许用于一次性兼容分支);
- 不要把 65% 之类的目标值重新写成 CI 的 warning 检查——目标应该进文档,门槛应该进代码。

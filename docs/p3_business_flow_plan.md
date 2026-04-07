# P3: 高级业务流程与 GenUI 深度交互规划

本项目 P3 阶段的核心目标是将 AI 能力深化到具体的垂直业务领域（CRM & HR），通过 **高级 GenUI 渲染逻辑** 实现“对话即界面”的交互体验。

## 1. 核心应用场景 (Vertical Scenarios)

### CRM - 客户关系管理
*   **P3-CRM-1: 智能商机看板 (Sales Kanban)**
    *   *功能描述*: AI 根据上下文在聊天窗口内渲染出可拖拽的商机阶段看板（Leads to Closed）。
    *   *UI 难点*: 处理跨组件的状态同步，拖拽行为触发后端 Action 更新 Supabase 表。
*   **P3-CRM-2: 客户 360 视图面板 (Customer 360 Card)**
    *   *功能描述*: 聚合展示客户基础信息、最近沟通历史、待办事项。
    *   *UI 难点*: 包含折线图（消费趋势）和嵌套的小工具。

### HR - 人力资源管理
*   **P3-HR-1: 交互式多级审批流 (Advanced Approval Flow)**
    *   *功能描述*: 请假或物资申领时，实时展示审批进度链条（Stepper），支持经理在 UI 中直接操作。
    *   *UI 难点*: 动态根据后端流程定义渲染步骤节点。
*   **P3-HR-2: 员工入职自动化引导 (Onboarding Stepper)**
    *   *功能描述*: AI 生成一系列的任务检查清单，用户完成一项后 UI 实时更新。
    *   *UI 难点*: 本地乐观更新与 WebSocket 推送的一致性。

## 2. 关键技术演进 (Technical Architecture)

### 2.1 GenUI 状态机 (Stateful GenUI)
*   **挑战**: 传统的 GenUI 通常是单次渲染。
*   **方案**: 引入 `GenUIStateProvider`，封装 UI 组件内部的持久化逻辑。
    *   支持 `action_callback`：用户点击按钮后，由 UI 主动发起 AI 重建或数据库事务，而非仅仅等待 AI 返回。

### 2.2 实时数据流 (Streaming UI Updates)
*   **挑战**: AI 正在执行长时间任务（如生成报告）时，UI 处于真空。
*   **方案**: 引入 **Tool Progress UI**：
    *   在工具调用期间，UI 显示“正在检索 CRM 数据...”、“正在计算 Q3 销售额...”等带有进度条的临时卡片。

### 2.3 高级可视化组件库
*   引入 `recharts` 或 `visx` 封装一套专属于 AI 导出的图表组件（Bubble Chart, Funnel Chart）。

## 3. P3 任务清单 (Tasks)

1.  **[Infrastructure] [Done]** 建立了 `metadata.ts` 领域感知的组件注册表。
2.  **[CRM] [Done]** 实现了 `KanbanMini.tsx` 交互式商机看板及其拖拽逻辑。
3.  **[HR] [Done]** 实现了 `ApprovalFlow.tsx` 有状态可视化审批，支持实时操作。
4.  **[Core] [Done]** 实现了 `ExecutionPulse.tsx` 工具执行进度反馈组件并全局集成。
5.  **[Polish] [Done]** 引入了 `framer-motion` 高级转场动画，增强了业务流程的视觉冲击力。

---

*P3 阶段交付摘要 (2026-04-07):*
*系统已具备深度业务感知能力，从“单向输出”进化为“双向状态同步”的智能中台界面。*

---
> [!TIP]
> 建议先从 **HR 审批流** 入手，因为它的逻辑闭环最清晰（Action -> State Transfer -> UI Update）。

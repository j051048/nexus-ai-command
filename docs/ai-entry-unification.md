# AI 入口统一化规范

> 解决 GenUI 组件与传统页面作为平行入口并存的问题。

## 1. 问题陈述

### 当前状态

Nexus AI Command 存在两套并行的 UI 入口系统：

**传统页面（Router-based）：**
- `src/pages/CRMPage.tsx` — CRM 客户管理
- `src/pages/ContractManagement.tsx` — 合同管理
- `src/pages/FinanceCenter.tsx` — 财务中心
- `src/pages/OACenter.tsx` — OA 中心
- `src/pages/VMDDashboard.tsx` — VMD 看板
- ... 共 40+ 页面

**GenUI 组件（AI Chat 内渲染）：**
- `src/components/ai/genui/DataChart.tsx` — 数据图表
- `src/components/ai/genui/DataTable.tsx` — 数据表格
- `src/components/ai/genui/KanbanMini.tsx` — 看板迷你版
- `src/components/ai/genui/ApprovalFlow.tsx` — 审批流程
- `src/components/ai/genui/ContractPreview.tsx` — 合同预览
- ... 共 29 个 GenUI 组件

**问题：**

```
用户问 "显示本月销售数据"
    ├── AI Chat → 渲染 GenUI StatCards（数据快照，无法交互）
    └── 侧边栏 → 跳转 SalesPipeline 页面（完整功能，可操作）

两个入口，两套数据获取逻辑，两种交互体验。
```

- **数据不一致**：GenUI 组件和传统页面可能展示不同数据
- **功能割裂**：GenUI 是只读快照，传统页面有完整 CRUD
- **维护成本翻倍**：同一业务逻辑需在两处实现
- **用户困惑**：不知道该用 AI 还是传统界面

---

## 2. 设计原则

1. **AI 优先，页面兜底**：AI Chat 是主入口，传统页面是"详细视图"
2. **GenUI 是预览，页面是完整功能**：GenUI 负责展示 + 快捷操作，传统页面负责完整 CRUD
3. **数据源统一**：GenUI 和传统页面共享同一数据获取层
4. **渐进式体验**：GenUI 可一键"展开"为传统页面

---

## 3. 目标架构

### 3.1 URL 路由策略

```
/crm                      → 传统 CRM 页面（完整功能）
/crm?view=ai              → CRM 页面的 AI 视图（GenUI 增强）
/ai/chat                  → AI 对话页（GenUI 内联渲染）
/ai/chat?expand=crm       → AI 对话 + 侧边打开 CRM 页面
```

### 3.2 组件分层

```
┌─────────────────────────────────────────────────┐
│                   App Shell                      │
│  ┌───────────────┬─────────────────────────────┐ │
│  │  AI Chat      │     Content Area            │ │
│  │               │                             │ │
│  │  User: 显示   │  ┌─────────────────────┐   │ │
│  │  本月销售     │  │  Mode: AI / Full    │   │ │
│  │               │  ├─────────────────────┤   │ │
│  │  AI: 好的     │  │                     │   │ │
│  │  ┌─────────┐  │  │  AI Mode:           │   │ │
│  │  │GenUI    │──┼──│  → GenUI Component  │   │ │
│  │  │StatCards│  │  │  → Quick Actions    │   │ │
│  │  └─────────┘  │  │                     │   │ │
│  │               │  │  Full Mode:         │   │ │
│  │  [展开详情]───┼──│  → Traditional Page │   │ │
│  │               │  │  → Full CRUD        │   │ │
│  │               │  └─────────────────────┘   │ │
│  └───────────────┴─────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 3.3 数据流统一

```typescript
// src/services/dataLayer.ts — 统一数据获取层

interface DataLayerOptions {
  mode: 'summary' | 'full';  // GenUI 用 summary，页面用 full
  filters?: Record<string, unknown>;
  pagination?: { page: number; pageSize: number };
}

// GenUI 和传统页面都调用同一个数据层
export async function fetchSalesData(options: DataLayerOptions) {
  const { mode, filters, pagination } = options;

  if (mode === 'summary') {
    // GenUI 模式：返回聚合数据
    return api.get('/api/sales/summary', { params: filters });
  }
  // Full 模式：返回分页明细
  return api.get('/api/sales/list', { params: { ...filters, ...pagination } });
}
```

---

## 4. 组件映射表

### GenUI 组件 → 传统页面映射

| GenUI 组件 | 传统页面 | 统一入口 | 状态 |
|------------|----------|----------|------|
| `StatCards` | `Index.tsx` (Dashboard) | `/dashboard` | Phase 1 |
| `DataChart` | `ReportsPage.tsx` | `/reports` | Phase 1 |
| `DataTable` | 各业务列表页 | 按业务 | Phase 1 |
| `KanbanMini` | `SalesPipeline.tsx` | `/sales` | Phase 1 |
| `TodoList` | `OACenter.tsx` | `/oa` | Phase 2 |
| `Timeline` | `SalesHistoryPanel.tsx` | `/crm/:id` | Phase 2 |
| `ApprovalFlow` | `ApprovalCenter` (component) | `/approvals` | Phase 2 |
| `ContractPreview` | `ContractManagement.tsx` | `/contracts` | Phase 2 |
| `FormBuilder` | `FormDesigner.tsx` | `/forms` | Phase 3 |
| `OrgChart` | `OrgChartPage.tsx` | `/org` | Phase 3 |
| `CalendarView` | 待建 | `/calendar` | Phase 3 |
| `GanttChart` | `ProjectManagement.tsx` | `/projects` | Phase 3 |
| `PieChart` | `ReportsPage.tsx` | `/reports` | Phase 1 |
| `FunnelChart` | `ReportsPage.tsx` | `/reports` | Phase 1 |
| `ComparisonTable` | `ReportsPage.tsx` | `/reports` | Phase 2 |
| `StatusTimeline` | `VMDDashboard.tsx` | `/vmd` | Phase 2 |
| `MetricComparison` | `TargetDashboard.tsx` | `/targets` | Phase 2 |
| `AlertList` | `NotificationCenter.tsx` | `/notifications` | Phase 2 |
| `UserProfileCard` | `ProfileCenter.tsx` | `/profile` | Phase 3 |
| `ProgressTracker` | `VMDTaskCenter.tsx` | `/vmd/tasks` | Phase 3 |
| `QuoteCard` | `ContractManagement.tsx` | `/contracts` | Phase 3 |
| `FileList` | `documents` router | `/documents` | Phase 3 |
| `InvoiceCard` | `FinanceCenter.tsx` | `/finance` | Phase 3 |
| `GeoChart` | `ReportsPage.tsx` | `/reports` | Phase 3 |
| `ReportCard` | `ReportsPage.tsx` | `/reports` | Phase 2 |
| `EmailDraft` | `InboxPage.tsx` | `/inbox` | Phase 3 |
| `DataGrid` | 各业务列表页 | 按业务 | Phase 2 |
| `Heatmap` | `ReportsPage.tsx` | `/reports` | Phase 3 |

### 共享业务组件（已存在于 GenUI 注册表和传统页面）

| 组件 | GenUI 注册名 | 传统来源 |
|------|-------------|----------|
| `BadgePanel` | `BadgePanel` | `dashboard/employee/BadgePanel` |
| `ApprovalCenter` | `ApprovalCenter` | `approval/ApprovalCenter` |
| `RewardsWallet` | `RewardsWallet` | `rewards/RewardsWallet` |
| `KanbanBoard` | `KanbanBoard` | `sales/sections/KanbanBoard` |
| `PriorityLeads` | `PriorityLeads` | `sales/sections/PriorityLeads` |

---

## 5. 迁移计划

### Phase 1：共存 + 明确 UX（第 1-4 周）

**目标：** 不改现有代码，通过 UI 引导解决用户困惑。

1. **GenUI 添加"查看详情"按钮**

```typescript
// GenUIContainer.tsx 中为每个 GenUI 组件添加 deepLink
const DEEP_LINKS: Record<string, string> = {
  StatCards: '/dashboard',
  DataChart: '/reports',
  KanbanMini: '/sales',
  ApprovalFlow: '/approvals',
  ContractPreview: '/contracts',
  // ...
};
```

2. **传统页面添加"AI 总结"入口**

在每个传统页面顶部添加一个"AI 问答"浮动按钮，点击后发送预置 prompt 到 AI Chat。

3. **统一数据服务层**

创建 `src/services/dataLayer.ts`，让 GenUI 组件和传统页面调用相同的 API。

### Phase 2：深度整合（第 5-8 周）

**目标：** GenUI 组件可直接操作数据，传统页面可嵌入 AI。

1. **GenUI 添加快捷操作**

```typescript
// 例如 KanbanMini 添加拖拽改状态
// DataTable 添加行内编辑
// ApprovalFlow 添加一键审批
```

2. **传统页面嵌入 AI 上下文面板**

```typescript
// 在 CRMPage 右侧添加 AI Copilot 面板
// 自动根据当前页面上下文提供建议
<AICopilotPanel context={{ page: 'crm', entity: selectedCustomer }} />
```

3. **侧边栏快捷跳转**

AI Chat 中的 GenUI 组件支持"全屏展开"，直接在右侧面板打开对应的传统页面。

### Phase 3：统一架构（第 9-12 周）

**目标：** GenUI 和传统页面使用同一套组件系统。

1. **组件双模式**

```typescript
interface SalesViewProps {
  mode: 'compact' | 'full';  // compact=GenUI, full=传统页面
  data: SalesData;
  onAction?: (action: Action) => void;
}

export function SalesView({ mode, data, onAction }: SalesViewProps) {
  if (mode === 'compact') {
    return <SalesCompactView data={data} onExpand={() => navigate('/sales')} />;
  }
  return <SalesFullView data={data} onAction={onAction} />;
}
```

2. **路由统一**

```typescript
// 同一路由，根据来源切换模式
<Route path="/sales" element={
  <SalesView mode={searchParams.get('view') === 'ai' ? 'compact' : 'full'} />
} />
```

---

## 6. 技术约束

1. **不破坏现有功能**：所有改动必须向后兼容
2. **懒加载不变**：GenUI 组件继续使用 `lazyWithRetry` 加载
3. **SSE 协议不变**：后端 `genui_render` 事件格式不变
4. **移动端优先**：GenUI 在移动端是主要入口，传统页面是桌面端主入口

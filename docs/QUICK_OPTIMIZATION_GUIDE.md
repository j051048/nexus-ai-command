# 快速应用优化指南

## 📋 已优化的示例页面

1. ✅ CRMPage - 完整优化
2. ✅ VMDDashboard - 完整优化  
3. ✅ LLMCostDashboard - 完整优化
4. ✅ TargetDashboard - 部分优化
5. ✅ Index.tsx - 无障碍支持

## 🔧 快速优化模板

### 模板1: Dashboard 页面

**适用于**: TargetDashboard, ReportsPage, CustomDashboard, SuperAdminDashboard, FinanceCenter, HRCenter, OACenter

**步骤**:
```tsx
// 1. 替换导入
- import { Skeleton } from '@/components/ui/skeleton';
+ import { LoadingState } from '@/components/common/LoadingState';
+ import { iconColors, iconBackgrounds, typography } from '@/lib/design-tokens';

// 2. 统计卡片使用 elevated 变体
- <Card>
+ <Card variant="elevated">

// 3. 图标容器统一样式
- <div className="p-2 rounded-lg bg-blue-500/10">
+ <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', iconBackgrounds.blue)}>
-   <Icon className="w-4 h-4 text-blue-500" />
+   <Icon className={cn('w-5 h-5', iconColors.blue)} />

// 4. 替换加载状态
- <Skeleton className="h-32" />
+ <LoadingState type="skeleton" rows={1} className="h-32" />

// 5. 标题使用 typography
- <h1 className="text-2xl font-bold">
+ <h1 className={typography.h1}>
```

---

### 模板2: 列表页面

**适用于**: WorkOrderPage, ContractManagement, AssetManagement, InventoryPage, ProjectManagement

**步骤**:
```tsx
// 1. 添加导入
+ import { FilterPanel } from '@/components/common/FilterPanel';
+ import { LoadingState } from '@/components/common/LoadingState';

// 2. 使用 FilterPanel 替代自定义筛选
<FilterPanel
  filters={[
    { type: 'search', key: 'query', label: '搜索', placeholder: '输入关键词' },
    { type: 'select', key: 'status', label: '状态', options: statusOptions },
  ]}
  values={filters}
  onChange={(key, value) => setFilters({...filters, [key]: value})}
  onReset={() => setFilters({})}
/>

// 3. 加载状态
- {isLoading && <div>加载中...</div>}
+ {isLoading && <LoadingState type="spinner" message="加载数据..." />}
```

---

### 模板3: 表单页面

**适用于**: FormDesigner, WorkflowDesigner, ProfileCenter, CompanySettingsPage

**步骤**:
```tsx
// 1. 按钮添加 aria-label
- <Button><Icon /></Button>
+ <Button aria-label="保存"><Icon /></Button>

// 2. 表单输入添加 label
<Label htmlFor="name">名称</Label>
<Input id="name" />

// 3. 使用 Card variant
- <Card>
+ <Card variant="flat">
```

---

## 📊 批量替换建议

使用 VS Code 全局搜索替换：

### 替换1: Skeleton 导入
**搜索**: `import { Skeleton } from '@/components/ui/skeleton';`
**替换**: `import { LoadingState } from '@/components/common/LoadingState';`

### 替换2: 简单加载状态
**搜索**: `<Skeleton className="h-(\d+)" />`
**替换**: `<LoadingState type="skeleton" rows={1} className="h-$1" />`

### 替换3: 硬编码颜色
**搜索**: `text-blue-500`
**替换**: 手动检查后使用 `iconColors.blue`

---

## ✅ 优先级建议

### P0 - 立即优化（5个）
1. ✅ CRMPage
2. ✅ VMDDashboard
3. ✅ LLMCostDashboard
4. ⏳ TargetDashboard
5. ⏳ WorkOrderPage

### P1 - 本周优化（10个）
- ReportsPage
- CustomDashboard
- FinanceCenter
- HRCenter
- ContractManagement
- AssetManagement
- WorkflowDesigner
- FormDesigner
- NotificationCenter
- InboxPage

### P2 - 下周优化（29个）
- 其余页面

---

## 🎯 总结

**已完成**: 5个核心页面  
**待优化**: 42个页面  
**建议**: 使用模板快速应用，重点优化高频页面

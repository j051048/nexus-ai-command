# 产品导览集成指南

## 已完成
- ✅ 安装 react-joyride
- ✅ 创建 ProductTour 组件
- ✅ 在 App.tsx 中集成

## 需要添加的 data-tour 属性

在以下组件中添加对应的 `data-tour` 属性：

### 1. 聊天框
文件：`src/components/chat/ChatInterface.tsx` 或类似文件
```tsx
<div data-tour="chat" className="...">
  {/* 聊天输入框 */}
</div>
```

### 2. 侧边栏
文件：`src/components/layout/Sidebar.tsx` 或 `DashboardLayout`
```tsx
<aside data-tour="sidebar" className="...">
  {/* 导航菜单 */}
</aside>
```

### 3. 仪表盘
文件：`src/components/dashboard/EmployeeDashboard.tsx`
```tsx
<div data-tour="dashboard" className="...">
  {/* 仪表盘内容 */}
</div>
```

### 4. 用户头像/设置
文件：`src/components/layout/Header.tsx` 或类似文件
```tsx
<button data-tour="profile" className="...">
  {/* 用户头像 */}
</button>
```

## 使用说明

1. 首次登录用户会自动看到导览
2. 导览完成后会记录到 localStorage
3. 用户可以跳过导览
4. 如需重新触发，清除 localStorage 中的 `hasSeenTour` 键

## 自定义导览步骤

编辑 `src/components/common/ProductTour.tsx` 中的 `tourSteps` 数组即可添加/修改步骤。

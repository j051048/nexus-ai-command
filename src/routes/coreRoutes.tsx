import React from "react";
import { Route, Navigate } from "react-router-dom";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";
import {
  EmployeeDashboard,
  BossDashboard,
  ApprovalCenter,
  SalesPipeline,
  ProjectManagement,
  ProjectDetail,
  ExceptionsPage,
  RewardsWallet,
  SalesTargetManager,
  TargetDashboard,
  InboxPage,
  ProfileCenter,
} from "./lazyImports";

export function coreRoutes(AdminRoute: React.ComponentType<{ children: React.ReactNode; allowedRoles?: string[] }>) {
  return (
    <>
      <Route index element={<Navigate to="/dashboard" replace />} />
      <Route path="dashboard" element={<ModuleErrorBoundary moduleName="仪表盘"><EmployeeDashboard /></ModuleErrorBoundary>} />
      <Route path="boss-dashboard" element={<ModuleErrorBoundary moduleName="管理驾驶舱"><BossDashboard /></ModuleErrorBoundary>} />
      <Route path="inbox" element={<ModuleErrorBoundary moduleName="待办中心"><InboxPage /></ModuleErrorBoundary>} />
      <Route path="approval" element={<ModuleErrorBoundary moduleName="审批中心"><ApprovalCenter /></ModuleErrorBoundary>} />
      <Route path="sales" element={<ModuleErrorBoundary moduleName="销售管道"><SalesPipeline /></ModuleErrorBoundary>} />
      <Route path="projects" element={<ModuleErrorBoundary moduleName="项目管理"><ProjectManagement /></ModuleErrorBoundary>} />
      <Route path="projects/:id" element={<ModuleErrorBoundary moduleName="项目详情"><ProjectDetail /></ModuleErrorBoundary>} />
      <Route path="exceptions" element={<ModuleErrorBoundary moduleName="异常管理"><ExceptionsPage /></ModuleErrorBoundary>} />
      <Route path="rewards" element={<ModuleErrorBoundary moduleName="奖励钱包"><RewardsWallet /></ModuleErrorBoundary>} />
      <Route path="targets" element={<ModuleErrorBoundary moduleName="销售目标"><SalesTargetManager /></ModuleErrorBoundary>} />
      <Route path="target-dashboard" element={<ModuleErrorBoundary moduleName="目标仪表盘"><TargetDashboard /></ModuleErrorBoundary>} />
      <Route path="personal-settings" element={<ModuleErrorBoundary moduleName="个人中心"><ProfileCenter /></ModuleErrorBoundary>} />
    </>
  );
}

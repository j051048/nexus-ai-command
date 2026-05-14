import React from "react";
import { Navigate, Route } from "react-router-dom";
import { ModuleRouteBoundary } from "@/components/common/ModuleRouteBoundary";
import {
  ApprovalCenter,
  BossDashboard,
  EmployeeDashboard,
  ExceptionsPage,
  InboxPage,
  ProfileCenter,
  ProjectDetail,
  ProjectManagement,
  RewardsWallet,
  SalesPipeline,
  SalesTargetManager,
  TargetDashboard,
} from "./lazyImports";

function routeBoundary(moduleName: string, child: React.ReactNode) {
  return <ModuleRouteBoundary moduleName={moduleName}>{child}</ModuleRouteBoundary>;
}

export function coreRoutes(
  _AdminRoute: React.ComponentType<{
    children: React.ReactNode;
    allowedRoles?: string[];
  }>,
) {
  return (
    <>
      <Route index element={<Navigate to="/dashboard" replace />} />
      <Route path="dashboard" element={routeBoundary("仪表盘", <EmployeeDashboard />)} />
      <Route path="boss-dashboard" element={routeBoundary("管理驾驶舱", <BossDashboard />)} />
      <Route path="inbox" element={routeBoundary("待办中心", <InboxPage />)} />
      <Route path="approval" element={routeBoundary("审批中心", <ApprovalCenter />)} />
      <Route path="sales" element={routeBoundary("销售管道", <SalesPipeline />)} />
      <Route path="projects" element={routeBoundary("项目管理", <ProjectManagement />)} />
      <Route path="projects/:id" element={routeBoundary("项目详情", <ProjectDetail />)} />
      <Route path="exceptions" element={routeBoundary("异常管理", <ExceptionsPage />)} />
      <Route path="rewards" element={routeBoundary("奖励钱包", <RewardsWallet />)} />
      <Route path="targets" element={routeBoundary("销售目标", <SalesTargetManager />)} />
      <Route path="target-dashboard" element={routeBoundary("目标仪表盘", <TargetDashboard />)} />
      <Route path="personal-settings" element={routeBoundary("个人中心", <ProfileCenter />)} />
    </>
  );
}

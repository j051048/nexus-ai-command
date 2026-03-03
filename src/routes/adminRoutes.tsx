import React from "react";
import { Route } from "react-router-dom";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";
import {
  AISettingsPanel,
  EmployeeManagement,
  DepartmentManagement,
  AuditPanel,
  SuperAdminDashboard,
  APIKeysPage,
  CompanySettingsPage,
  OrgChartPage,
  PluginMarketplace,
  LLMModelManagement,
  LLMCostDashboard,
  AgentDebugPanel,
  AnimationShowcase,
  OACenter,
  HRCenter,
  FinanceCenter,
  ProfileCenter,
  WorkflowList,
  WorkflowDesigner,
  WorkflowTemplates,
  FormDesigner,
  CustomDashboard,
  NotificationCenter,
  ReportsPage,
  PaymentPage,
} from "./lazyImports";

export function adminRoutes(AdminRoute: React.ComponentType<{ children: React.ReactNode; allowedRoles?: string[] }>) {
  return (
    <>
      {/* Enterprise Management */}
      <Route path="oa" element={<ModuleErrorBoundary moduleName="OA办公"><OACenter /></ModuleErrorBoundary>} />
      <Route path="hr" element={<ModuleErrorBoundary moduleName="人力资源"><HRCenter /></ModuleErrorBoundary>} />
      <Route path="finance" element={<ModuleErrorBoundary moduleName="财务中心"><FinanceCenter /></ModuleErrorBoundary>} />
      <Route path="profile" element={<ModuleErrorBoundary moduleName="个人中心"><ProfileCenter /></ModuleErrorBoundary>} />

      {/* Workflows */}
      <Route path="workflows" element={<ModuleErrorBoundary moduleName="工作流"><WorkflowList /></ModuleErrorBoundary>} />
      <Route path="workflows/new" element={<ModuleErrorBoundary moduleName="工作流设计"><WorkflowDesigner /></ModuleErrorBoundary>} />
      <Route path="workflows/:id" element={<ModuleErrorBoundary moduleName="工作流设计"><WorkflowDesigner /></ModuleErrorBoundary>} />
      <Route path="workflow-templates" element={<ModuleErrorBoundary moduleName="工作流模板"><WorkflowTemplates /></ModuleErrorBoundary>} />
      <Route path="form-designer" element={<ModuleErrorBoundary moduleName="表单设计"><FormDesigner /></ModuleErrorBoundary>} />
      <Route path="form-designer/:id" element={<ModuleErrorBoundary moduleName="表单设计"><FormDesigner /></ModuleErrorBoundary>} />

      {/* Dashboards & Reports */}
      <Route path="custom-dashboard" element={<ModuleErrorBoundary moduleName="自定义仪表盘"><CustomDashboard /></ModuleErrorBoundary>} />
      <Route path="notification-center" element={<ModuleErrorBoundary moduleName="消息中心"><NotificationCenter /></ModuleErrorBoundary>} />
      <Route path="reports" element={<ModuleErrorBoundary moduleName="报表"><ReportsPage /></ModuleErrorBoundary>} />
      <Route path="payments" element={<ModuleErrorBoundary moduleName="支付"><PaymentPage /></ModuleErrorBoundary>} />

      {/* Admin only */}
      <Route path="settings" element={<ModuleErrorBoundary moduleName="AI设置"><AISettingsPanel /></ModuleErrorBoundary>} />
      <Route path="employees" element={<AdminRoute allowedRoles={['boss', 'manager']}><ModuleErrorBoundary moduleName="员工管理"><EmployeeManagement /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="departments" element={<ModuleErrorBoundary moduleName="部门管理"><DepartmentManagement /></ModuleErrorBoundary>} />
      <Route path="audit" element={<ModuleErrorBoundary moduleName="审计面板"><AuditPanel /></ModuleErrorBoundary>} />
      <Route path="super-admin" element={<AdminRoute><ModuleErrorBoundary moduleName="超级管理"><SuperAdminDashboard /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="api-keys" element={<AdminRoute><ModuleErrorBoundary moduleName="API密钥"><APIKeysPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="company-settings" element={<AdminRoute><ModuleErrorBoundary moduleName="企业设置"><CompanySettingsPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="org-chart" element={<AdminRoute><ModuleErrorBoundary moduleName="组织架构"><OrgChartPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="plugins" element={<ModuleErrorBoundary moduleName="插件市场"><PluginMarketplace /></ModuleErrorBoundary>} />
      <Route path="llm/models" element={<AdminRoute><ModuleErrorBoundary moduleName="LLM模型"><LLMModelManagement /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="llm/costs" element={<AdminRoute><ModuleErrorBoundary moduleName="LLM成本"><LLMCostDashboard /></ModuleErrorBoundary></AdminRoute>} />

      {/* Developer Tools */}
      <Route path="dev/animations" element={<AnimationShowcase />} />
      <Route path="agent-debug" element={<AdminRoute><ModuleErrorBoundary moduleName="调试面板"><AgentDebugPanel /></ModuleErrorBoundary></AdminRoute>} />
    </>
  );
}

import React from "react";
import { Route, Navigate } from "react-router-dom";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";
import {
  AISettingsPanel,

  AuditPanel,
  SuperAdminDashboard,
  APIKeysPage,
  CompanySettingsPage,
  OrgChartPage,
  PluginMarketplace,
  LLMModelManagement,
  LLMCostDashboard,
  SoulDocumentPage,
  AgentRunsPage,
  ToolGovernancePage,
  AgentDebugPanel,
  AnimationShowcase,
  ScheduledTasks,
  OACenter,
  HRCenter,
  FinanceCenter,
  ProfileCenter,
  IntentRulesPage,
  WorkflowList,
  WorkflowDesigner,
  WorkflowTemplates,
  FormDesigner,
  CustomDashboard,
  NotificationCenter,
  ReportsPage,
  ReportBuilderPage,
  PaymentPage,
  AssetManagement,
  CertificateManagement,
  BillingDashboard,
  CheckoutSuccessPage,
  CheckoutCancelPage,
  AiRoiDashboard,
} from "./lazyImports";

export function adminRoutes(AdminRoute: React.ComponentType<{ children: React.ReactNode; allowedRoles?: string[] }>) {
  return (
    <>
      {/* Enterprise Management - requires manager+ role */}
      <Route path="oa" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="OA办公"><OACenter /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="assets" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="资产管理"><AssetManagement /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="certificates" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="证照管理"><CertificateManagement /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="hr" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="人力资源"><HRCenter /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="finance" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="财务中心"><FinanceCenter /></ModuleErrorBoundary></AdminRoute>} />

      {/* Workflows - requires manager+ role */}
      <Route path="workflows" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="工作流"><WorkflowList /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="workflows/new" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="工作流设计"><WorkflowDesigner /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="workflows/:id" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="工作流设计"><WorkflowDesigner /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="workflow-templates" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="工作流模板"><WorkflowTemplates /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="form-designer" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="表单设计"><FormDesigner /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="form-designer/:id" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="表单设计"><FormDesigner /></ModuleErrorBoundary></AdminRoute>} />

      {/* Dashboards & Reports */}
      <Route path="custom-dashboard" element={<ModuleErrorBoundary moduleName="自定义仪表盘"><CustomDashboard /></ModuleErrorBoundary>} />
      <Route path="notification-center" element={<ModuleErrorBoundary moduleName="消息中心"><NotificationCenter /></ModuleErrorBoundary>} />
      <Route path="reports" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="报表"><ReportsPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="report-builder" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="报表构建"><ReportBuilderPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="payments" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="支付"><PaymentPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="billing" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="订阅管理"><BillingDashboard /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="billing/success" element={<CheckoutSuccessPage />} />
      <Route path="billing/canceled" element={<CheckoutCancelPage />} />

      {/* Admin only */}
      <Route path="settings" element={<AdminRoute><ModuleErrorBoundary moduleName="AI设置"><AISettingsPanel /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="employees" element={<Navigate to="/org-chart" replace />} />
      <Route path="departments" element={<Navigate to="/org-chart" replace />} />
      <Route path="audit" element={<AdminRoute><ModuleErrorBoundary moduleName="审计面板"><AuditPanel /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="super-admin" element={<AdminRoute><ModuleErrorBoundary moduleName="超级管理"><SuperAdminDashboard /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="api-keys" element={<AdminRoute><ModuleErrorBoundary moduleName="API密钥"><APIKeysPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="company-settings" element={<AdminRoute><ModuleErrorBoundary moduleName="企业设置"><CompanySettingsPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="soul-document" element={<AdminRoute><ModuleErrorBoundary moduleName="灵魂文档"><SoulDocumentPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="org-chart" element={<AdminRoute><ModuleErrorBoundary moduleName="组织架构"><OrgChartPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="plugins" element={<AdminRoute><ModuleErrorBoundary moduleName="插件市场"><PluginMarketplace /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="llm/models" element={<AdminRoute><ModuleErrorBoundary moduleName="LLM模型"><LLMModelManagement /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="llm/costs" element={<AdminRoute><ModuleErrorBoundary moduleName="LLM成本"><LLMCostDashboard /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="agent-runs" element={<AdminRoute allowedRoles={['boss', 'founder', 'admin']}><ModuleErrorBoundary moduleName="Agent Run"><AgentRunsPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="tools/governance" element={<AdminRoute allowedRoles={['boss', 'founder', 'admin']}><ModuleErrorBoundary moduleName="Tool Governance"><ToolGovernancePage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="ai-roi" element={<AdminRoute allowedRoles={['boss', 'founder', 'manager']}><ModuleErrorBoundary moduleName="AI ROI"><AiRoiDashboard /></ModuleErrorBoundary></AdminRoute>} />

      {/* Developer Tools */}
      <Route path="dev/animations" element={<AnimationShowcase />} />
      <Route path="agent-debug" element={<AdminRoute><ModuleErrorBoundary moduleName="调试面板"><AgentDebugPanel /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="scheduled-tasks" element={<AdminRoute><ModuleErrorBoundary moduleName="定时任务"><ScheduledTasks /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="admin/intent-rules" element={<AdminRoute><ModuleErrorBoundary moduleName="意图规则"><IntentRulesPage /></ModuleErrorBoundary></AdminRoute>} />
    </>
  );
}

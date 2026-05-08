import React from "react";
import { Navigate, Route } from "react-router-dom";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";
import type { ModuleFlag } from "@/config/featureFlags";
import { ModuleGate } from "./ModuleGate";
import {
  AgentDebugPanel,
  AgentRunsPage,
  AISettingsPanel,
  AiRoiDashboard,
  AnimationShowcase,
  APIKeysPage,
  AssetManagement,
  AuditPanel,
  BillingDashboard,
  CertificateManagement,
  CheckoutCancelPage,
  CheckoutSuccessPage,
  CompanySettingsPage,
  CustomDashboard,
  FinanceCenter,
  FormDesigner,
  HRCenter,
  IntentRulesPage,
  LLMCostDashboard,
  LLMModelManagement,
  NotificationCenter,
  OACenter,
  OrgChartPage,
  PaymentPage,
  PluginMarketplace,
  ReportBuilderPage,
  ReportsPage,
  ScheduledTasks,
  SoulDocumentPage,
  SuperAdminDashboard,
  ToolGovernancePage,
  WorkflowDesigner,
  WorkflowList,
  WorkflowTemplates,
} from "./lazyImports";

type AdminRouteComponent = React.ComponentType<{
  children: React.ReactNode;
  allowedRoles?: string[];
}>;

function moduleBoundary(flag: ModuleFlag, moduleName: string, child: React.ReactNode) {
  return (
    <ModuleGate flag={flag}>
      <ModuleErrorBoundary moduleName={moduleName}>{child}</ModuleErrorBoundary>
    </ModuleGate>
  );
}

function adminModule(
  AdminRoute: AdminRouteComponent,
  flag: ModuleFlag,
  moduleName: string,
  child: React.ReactNode,
  allowedRoles?: string[],
) {
  return (
    <ModuleGate flag={flag}>
      <AdminRoute allowedRoles={allowedRoles}>
        <ModuleErrorBoundary moduleName={moduleName}>{child}</ModuleErrorBoundary>
      </AdminRoute>
    </ModuleGate>
  );
}

export function adminRoutes(AdminRoute: AdminRouteComponent) {
  const managerRoles = ["boss", "founder", "manager"];
  const adminRoles = ["boss", "founder", "admin"];

  return (
    <>
      <Route path="oa" element={adminModule(AdminRoute, "oa", "OA", <OACenter />, managerRoles)} />
      <Route path="assets" element={adminModule(AdminRoute, "assets", "Assets", <AssetManagement />, managerRoles)} />
      <Route path="certificates" element={adminModule(AdminRoute, "certificates", "Certificates", <CertificateManagement />, managerRoles)} />
      <Route path="hr" element={adminModule(AdminRoute, "hr", "HR", <HRCenter />, managerRoles)} />
      <Route path="finance" element={adminModule(AdminRoute, "finance", "Finance", <FinanceCenter />, managerRoles)} />

      <Route path="workflows" element={adminModule(AdminRoute, "workflow_designer", "Workflows", <WorkflowList />, managerRoles)} />
      <Route path="workflows/new" element={adminModule(AdminRoute, "workflow_designer", "Workflow Designer", <WorkflowDesigner />, managerRoles)} />
      <Route path="workflows/:id" element={adminModule(AdminRoute, "workflow_designer", "Workflow Designer", <WorkflowDesigner />, managerRoles)} />
      <Route path="workflow-templates" element={adminModule(AdminRoute, "workflow_designer", "Workflow Templates", <WorkflowTemplates />, managerRoles)} />
      <Route path="form-designer" element={adminModule(AdminRoute, "form_designer", "Form Designer", <FormDesigner />, managerRoles)} />
      <Route path="form-designer/:id" element={adminModule(AdminRoute, "form_designer", "Form Designer", <FormDesigner />, managerRoles)} />

      <Route path="custom-dashboard" element={moduleBoundary("custom_dashboard", "Custom Dashboard", <CustomDashboard />)} />
      <Route path="notification-center" element={<ModuleErrorBoundary moduleName="Notification Center"><NotificationCenter /></ModuleErrorBoundary>} />
      <Route path="reports" element={adminModule(AdminRoute, "reports", "Reports", <ReportsPage />, managerRoles)} />
      <Route path="report-builder" element={adminModule(AdminRoute, "report_builder", "Report Builder", <ReportBuilderPage />, managerRoles)} />
      <Route path="payments" element={adminModule(AdminRoute, "billing", "Payments", <PaymentPage />, managerRoles)} />
      <Route path="billing" element={adminModule(AdminRoute, "billing", "Billing", <BillingDashboard />, managerRoles)} />
      <Route path="billing/success" element={<CheckoutSuccessPage />} />
      <Route path="billing/canceled" element={<CheckoutCancelPage />} />

      <Route path="settings" element={<AdminRoute><ModuleErrorBoundary moduleName="AI Settings"><AISettingsPanel /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="employees" element={<Navigate to="/org-chart" replace />} />
      <Route path="departments" element={<Navigate to="/org-chart" replace />} />
      <Route path="audit" element={<AdminRoute><ModuleErrorBoundary moduleName="Audit"><AuditPanel /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="super-admin" element={<AdminRoute><ModuleErrorBoundary moduleName="Super Admin"><SuperAdminDashboard /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="api-keys" element={<AdminRoute><ModuleErrorBoundary moduleName="API Keys"><APIKeysPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="company-settings" element={<AdminRoute><ModuleErrorBoundary moduleName="Company Settings"><CompanySettingsPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="soul-document" element={adminModule(AdminRoute, "soul_document", "Soul Document", <SoulDocumentPage />)} />
      <Route path="org-chart" element={<AdminRoute><ModuleErrorBoundary moduleName="Org Chart"><OrgChartPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="plugins" element={adminModule(AdminRoute, "plugins", "Plugin Marketplace", <PluginMarketplace />)} />
      <Route path="llm/models" element={<AdminRoute><ModuleErrorBoundary moduleName="LLM Models"><LLMModelManagement /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="llm/costs" element={<AdminRoute><ModuleErrorBoundary moduleName="LLM Costs"><LLMCostDashboard /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="agent-runs" element={<AdminRoute allowedRoles={adminRoles}><ModuleErrorBoundary moduleName="Agent Runs"><AgentRunsPage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="tools/governance" element={<AdminRoute allowedRoles={adminRoles}><ModuleErrorBoundary moduleName="Tool Governance"><ToolGovernancePage /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="ai-roi" element={<AdminRoute allowedRoles={managerRoles}><ModuleErrorBoundary moduleName="AI ROI"><AiRoiDashboard /></ModuleErrorBoundary></AdminRoute>} />

      <Route path="dev/animations" element={<ModuleGate flag="dev_tools"><AnimationShowcase /></ModuleGate>} />
      <Route path="agent-debug" element={<ModuleGate flag="dev_tools"><AdminRoute><ModuleErrorBoundary moduleName="Agent Debug"><AgentDebugPanel /></ModuleErrorBoundary></AdminRoute></ModuleGate>} />
      <Route path="scheduled-tasks" element={<AdminRoute><ModuleErrorBoundary moduleName="Scheduled Tasks"><ScheduledTasks /></ModuleErrorBoundary></AdminRoute>} />
      <Route path="admin/intent-rules" element={<AdminRoute><ModuleErrorBoundary moduleName="Intent Rules"><IntentRulesPage /></ModuleErrorBoundary></AdminRoute>} />
    </>
  );
}

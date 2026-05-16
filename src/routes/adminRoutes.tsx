import React from "react";
import { Navigate, Route } from "react-router-dom";
import { ModuleRouteBoundary } from "@/components/common/ModuleRouteBoundary";
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
  DeploymentReadinessPage,
  CustomerSuccessPage,
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
  PermissionMatrixPage,
  PluginMarketplace,
  ReportBuilderPage,
  ReportsPage,
  ScheduledTasks,
  SoulDocumentPage,
  SLODashboard,
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
      <ModuleRouteBoundary moduleName={moduleName}>{child}</ModuleRouteBoundary>
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
        <ModuleRouteBoundary moduleName={moduleName}>{child}</ModuleRouteBoundary>
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
      <Route path="notification-center" element={<ModuleRouteBoundary moduleName="Notification Center"><NotificationCenter /></ModuleRouteBoundary>} />
      <Route path="reports" element={adminModule(AdminRoute, "reports", "Reports", <ReportsPage />, managerRoles)} />
      <Route path="report-builder" element={adminModule(AdminRoute, "report_builder", "Report Builder", <ReportBuilderPage />, managerRoles)} />
      <Route path="payments" element={adminModule(AdminRoute, "billing", "Payments", <PaymentPage />, managerRoles)} />
      <Route path="billing" element={adminModule(AdminRoute, "billing", "Billing", <BillingDashboard />, managerRoles)} />
      <Route path="billing/success" element={<CheckoutSuccessPage />} />
      <Route path="billing/canceled" element={<CheckoutCancelPage />} />

      <Route path="settings" element={<AdminRoute><ModuleRouteBoundary moduleName="AI Settings"><AISettingsPanel /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="employees" element={<Navigate to="/org-chart" replace />} />
      <Route path="departments" element={<Navigate to="/org-chart" replace />} />
      <Route path="audit" element={<AdminRoute><ModuleRouteBoundary moduleName="Audit"><AuditPanel /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="super-admin" element={<Navigate to="/admin" replace />} />
      <Route path="api-keys" element={<AdminRoute><ModuleRouteBoundary moduleName="API Keys"><APIKeysPage /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="company-settings" element={<AdminRoute><ModuleRouteBoundary moduleName="Company Settings"><CompanySettingsPage /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="soul-document" element={adminModule(AdminRoute, "soul_document", "Soul Document", <SoulDocumentPage />)} />
      <Route path="org-chart" element={<AdminRoute><ModuleRouteBoundary moduleName="Org Chart"><OrgChartPage /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="plugins" element={adminModule(AdminRoute, "plugins", "Plugin Marketplace", <PluginMarketplace />)} />
      <Route path="llm/models" element={<AdminRoute><ModuleRouteBoundary moduleName="LLM Models"><LLMModelManagement /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="llm/costs" element={<AdminRoute><ModuleRouteBoundary moduleName="LLM Costs"><LLMCostDashboard /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="agent-runs" element={<AdminRoute allowedRoles={adminRoles}><ModuleRouteBoundary moduleName="Agent Runs"><AgentRunsPage /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="slo" element={<AdminRoute allowedRoles={adminRoles}><ModuleRouteBoundary moduleName="SLO Dashboard"><SLODashboard /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="deployment-readiness" element={<AdminRoute allowedRoles={adminRoles}><ModuleRouteBoundary moduleName="Deployment Readiness"><DeploymentReadinessPage /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="permissions-matrix" element={<AdminRoute allowedRoles={adminRoles}><ModuleRouteBoundary moduleName="Permission Matrix"><PermissionMatrixPage /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="tools/governance" element={<AdminRoute allowedRoles={adminRoles}><ModuleRouteBoundary moduleName="Tool Governance"><ToolGovernancePage /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="ai-roi" element={<AdminRoute allowedRoles={managerRoles}><ModuleRouteBoundary moduleName="AI ROI"><AiRoiDashboard /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="customer-success" element={<AdminRoute allowedRoles={managerRoles}><ModuleRouteBoundary moduleName="Customer Success"><CustomerSuccessPage /></ModuleRouteBoundary></AdminRoute>} />

      <Route path="dev/animations" element={<ModuleGate flag="dev_tools"><AnimationShowcase /></ModuleGate>} />
      <Route path="agent-debug" element={<ModuleGate flag="dev_tools"><AdminRoute><ModuleRouteBoundary moduleName="Agent Debug"><AgentDebugPanel /></ModuleRouteBoundary></AdminRoute></ModuleGate>} />
      <Route path="scheduled-tasks" element={<AdminRoute><ModuleRouteBoundary moduleName="Scheduled Tasks"><ScheduledTasks /></ModuleRouteBoundary></AdminRoute>} />
      <Route path="admin/intent-rules" element={<AdminRoute><ModuleRouteBoundary moduleName="Intent Rules"><IntentRulesPage /></ModuleRouteBoundary></AdminRoute>} />
    </>
  );
}

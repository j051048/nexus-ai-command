import React from "react";
import { Navigate, Route } from "react-router-dom";
import { ModuleRouteBoundary } from "@/components/common/ModuleRouteBoundary";
import ActionAnalyticsPage from "@/pages/ActionAnalyticsPage";
import {
  ApprovalCenter,
  AICenterPage,
  AIOperatingSystemPage,
  AgentImprovementCenterPage,
  BossDashboard,
  DataHubPage,
  EmployeeDashboard,
  ExceptionsPage,
  InboxPage,
  IndustryKnowledgePage,
  ProfileCenter,
  ProjectDetail,
  ProjectManagement,
  RewardsWallet,
  SalesPipeline,
  SalesTargetManager,
  TargetDashboard,
  WorkspaceHubPage,
} from "./lazyImports";

function routeBoundary(moduleName: string, child: React.ReactNode) {
  return <ModuleRouteBoundary moduleName={moduleName}>{child}</ModuleRouteBoundary>;
}

export function coreRoutes(
  AdminRoute: React.ComponentType<{
    children: React.ReactNode;
    allowedRoles?: string[];
  }>,
) {
  return (
    <>
      <Route index element={<Navigate to="/dashboard" replace />} />
      <Route path="dashboard" element={routeBoundary("Dashboard", <InboxPage />)} />
      <Route
        path="boss-dashboard"
        element={
          <AdminRoute allowedRoles={["boss", "founder"]}>
            {routeBoundary("Boss Dashboard", <BossDashboard />)}
          </AdminRoute>
        }
      />
      <Route path="inbox" element={routeBoundary("Inbox", <InboxPage />)} />
      <Route path="performance-dashboard" element={routeBoundary("Performance Dashboard", <EmployeeDashboard />)} />
      <Route path="workbench" element={routeBoundary("Workbench", <WorkspaceHubPage />)} />
      <Route path="data" element={routeBoundary("Data", <DataHubPage />)} />
      <Route path="action-analytics" element={routeBoundary("Action Analytics", <ActionAnalyticsPage />)} />
      <Route path="ai-center" element={routeBoundary("AI Center", <AICenterPage />)} />
      <Route path="ai-operating-system" element={routeBoundary("AI Operating System", <AIOperatingSystemPage />)} />
      <Route path="agent-improvement-center" element={routeBoundary("Agent Improvement Center", <AgentImprovementCenterPage />)} />
      <Route path="industry-knowledge" element={routeBoundary("Industry Knowledge", <IndustryKnowledgePage />)} />
      <Route path="approval" element={routeBoundary("Approval Center", <ApprovalCenter />)} />
      <Route path="sales" element={routeBoundary("Sales Pipeline", <SalesPipeline />)} />
      <Route path="projects" element={routeBoundary("Projects", <ProjectManagement />)} />
      <Route path="projects/:id" element={routeBoundary("Project Detail", <ProjectDetail />)} />
      <Route path="exceptions" element={routeBoundary("Exceptions", <ExceptionsPage />)} />
      <Route path="rewards" element={routeBoundary("Rewards", <RewardsWallet />)} />
      <Route path="targets" element={routeBoundary("Sales Targets", <SalesTargetManager />)} />
      <Route path="target-dashboard" element={routeBoundary("Target Dashboard", <TargetDashboard />)} />
      <Route path="personal-settings" element={routeBoundary("Profile", <ProfileCenter />)} />
    </>
  );
}

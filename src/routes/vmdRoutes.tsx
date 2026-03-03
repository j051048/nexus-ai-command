import React from "react";
import { Route } from "react-router-dom";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";
import {
  VMDCenter,
  VMDTaskCenter,
  VMDAgentConfig,
  VMDClueManagement,
  VMDCompliancePage,
  VMDDashboard,
} from "./lazyImports";

export function vmdRoutes() {
  return (
    <>
      <Route path="vmd" element={<ModuleErrorBoundary moduleName="VMD"><VMDCenter /></ModuleErrorBoundary>} />
      <Route path="vmd/tasks" element={<ModuleErrorBoundary moduleName="VMD任务"><VMDTaskCenter /></ModuleErrorBoundary>} />
      <Route path="vmd/agents" element={<ModuleErrorBoundary moduleName="VMD代理"><VMDAgentConfig /></ModuleErrorBoundary>} />
      <Route path="vmd/clues" element={<ModuleErrorBoundary moduleName="VMD线索"><VMDClueManagement /></ModuleErrorBoundary>} />
      <Route path="vmd/compliance" element={<ModuleErrorBoundary moduleName="VMD合规"><VMDCompliancePage /></ModuleErrorBoundary>} />
      <Route path="vmd/dashboard" element={<ModuleErrorBoundary moduleName="VMD仪表盘"><VMDDashboard /></ModuleErrorBoundary>} />
    </>
  );
}

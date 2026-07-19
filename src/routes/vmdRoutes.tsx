import React from "react";
import { Route } from "react-router-dom";
import { ModuleRouteBoundary } from "@/components/common/ModuleRouteBoundary";
import { ModuleGate } from "./ModuleGate";
import {
  VMDAgentConfig,
  VMDCenter,
  VMDClueManagement,
  VMDCompliancePage,
  VMDDashboard,
  VMDTaskCenter,
  SolutionWorkspacePage,
  TenderAnalysisPage,
} from "./lazyImports";

function vmdElement(moduleName: string, child: React.ReactNode) {
  return (
    <ModuleGate flag="vmd">
      <ModuleRouteBoundary moduleName={moduleName}>{child}</ModuleRouteBoundary>
    </ModuleGate>
  );
}

function tenderElement(child: React.ReactNode) {
  return (
    <ModuleGate flag="tender">
      <ModuleRouteBoundary moduleName="Tender Workspace">{child}</ModuleRouteBoundary>
    </ModuleGate>
  );
}

export function vmdRoutes() {
  return (
    <>
      <Route path="vmd" element={vmdElement("VMD", <VMDCenter />)} />
      <Route path="growth/radar" element={vmdElement("Growth Radar", <VMDCenter />)} />
      <Route path="growth/accounts" element={vmdElement("Growth Accounts", <VMDCenter />)} />
      <Route path="growth/solutions" element={vmdElement("Solution Workspace", <SolutionWorkspacePage />)} />
      <Route path="growth/tenders" element={tenderElement(<TenderAnalysisPage />)} />
      <Route path="growth/review" element={vmdElement("Growth Review", <VMDCenter />)} />
      <Route path="vmd/tasks" element={vmdElement("VMD Tasks", <VMDTaskCenter />)} />
      <Route path="vmd/agents" element={vmdElement("VMD Agents", <VMDAgentConfig />)} />
      <Route path="vmd/clues" element={vmdElement("VMD Clues", <VMDClueManagement />)} />
      <Route path="vmd/compliance" element={vmdElement("VMD Compliance", <VMDCompliancePage />)} />
      <Route path="vmd/dashboard" element={vmdElement("VMD Dashboard", <VMDDashboard />)} />
    </>
  );
}

import React from "react";
import { Route } from "react-router-dom";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";
import type { ModuleFlag } from "@/config/featureFlags";
import { ModuleGate } from "./ModuleGate";
import {
  BattlecardLibrary,
  ContractManagement,
  CRMPage,
  DataImportPage,
  DocumentsPage,
  InventoryPage,
  KnowledgeGraphPage,
  TenderAnalysisPage,
  TrainingCenter,
  WorkOrderPage,
} from "./lazyImports";

function guarded(flag: ModuleFlag, moduleName: string, child: React.ReactNode) {
  return (
    <ModuleGate flag={flag}>
      <ModuleErrorBoundary moduleName={moduleName}>{child}</ModuleErrorBoundary>
    </ModuleGate>
  );
}

export function businessRoutes() {
  return (
    <>
      <Route path="crm" element={guarded("crm", "CRM", <CRMPage />)} />
      <Route path="contracts" element={guarded("documents", "Contract Management", <ContractManagement />)} />
      <Route path="tender-analysis" element={guarded("tender", "Tender Analysis", <TenderAnalysisPage />)} />
      <Route path="battlecards" element={guarded("battlecards", "Battlecards", <BattlecardLibrary />)} />
      <Route path="documents" element={guarded("documents", "Documents", <DocumentsPage />)} />
      <Route path="knowledge" element={guarded("knowledge", "Knowledge Graph", <KnowledgeGraphPage />)} />
      <Route path="import" element={guarded("import", "Data Import", <DataImportPage />)} />
      <Route path="training" element={guarded("training", "Training Center", <TrainingCenter />)} />
      <Route path="work-orders" element={guarded("work_orders", "Work Orders", <WorkOrderPage />)} />
      <Route path="inventory" element={guarded("inventory", "Inventory", <InventoryPage />)} />
    </>
  );
}

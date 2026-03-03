import React from "react";
import { Route } from "react-router-dom";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";
import {
  CRMPage,
  ContractManagement,
  TenderAnalysisPage,
  BattlecardLibrary,
  DocumentsPage,
  DataImportPage,
  TrainingCenter,
} from "./lazyImports";

export function businessRoutes() {
  return (
    <>
      <Route path="crm" element={<ModuleErrorBoundary moduleName="CRM"><CRMPage /></ModuleErrorBoundary>} />
      <Route path="contracts" element={<ModuleErrorBoundary moduleName="合同管理"><ContractManagement /></ModuleErrorBoundary>} />
      <Route path="tender-analysis" element={<ModuleErrorBoundary moduleName="标书分析"><TenderAnalysisPage /></ModuleErrorBoundary>} />
      <Route path="battlecards" element={<ModuleErrorBoundary moduleName="竞品卡片"><BattlecardLibrary /></ModuleErrorBoundary>} />
      <Route path="documents" element={<ModuleErrorBoundary moduleName="知识库"><DocumentsPage /></ModuleErrorBoundary>} />
      <Route path="knowledge" element={<ModuleErrorBoundary moduleName="知识库"><DocumentsPage /></ModuleErrorBoundary>} />
      <Route path="import" element={<ModuleErrorBoundary moduleName="数据导入"><DataImportPage /></ModuleErrorBoundary>} />
      <Route path="training" element={<ModuleErrorBoundary moduleName="培训中心"><TrainingCenter /></ModuleErrorBoundary>} />
    </>
  );
}

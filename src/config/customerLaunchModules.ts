import type { ModuleFlag } from "./featureFlags";
import { CUSTOMER_LAUNCH_ENABLED_MODULES } from "./featureFlags";

export type CustomerLaunchModuleReadiness = {
  flag: ModuleFlag;
  owner: string;
  smokePath: string;
  smokeFlow: string;
};

export const ALL_CUSTOMER_LAUNCH_MODULE_READINESS: CustomerLaunchModuleReadiness[] = [
  { flag: "approval", owner: "workflow", smokePath: "/approval", smokeFlow: "submit-and-review-approval" },
  { flag: "assets", owner: "ops", smokePath: "/assets", smokeFlow: "asset-list-loads" },
  { flag: "battlecards", owner: "sales", smokePath: "/battlecards", smokeFlow: "battlecard-library-loads" },
  { flag: "billing", owner: "growth", smokePath: "/billing", smokeFlow: "billing-dashboard-loads" },
  { flag: "certificates", owner: "ops", smokePath: "/certificates", smokeFlow: "certificate-list-loads" },
  { flag: "crm", owner: "sales", smokePath: "/crm", smokeFlow: "crm-workspace-loads" },
  { flag: "custom_dashboard", owner: "analytics", smokePath: "/custom-dashboard", smokeFlow: "custom-dashboard-loads" },
  { flag: "documents", owner: "knowledge", smokePath: "/documents", smokeFlow: "documents-upload-list-loads" },
  { flag: "finance", owner: "finance", smokePath: "/finance", smokeFlow: "finance-center-loads" },
  { flag: "form_designer", owner: "workflow", smokePath: "/form-designer", smokeFlow: "form-designer-loads" },
  { flag: "hr", owner: "people", smokePath: "/hr", smokeFlow: "hr-center-loads" },
  { flag: "import", owner: "data", smokePath: "/import", smokeFlow: "data-import-loads" },
  { flag: "inventory", owner: "ops", smokePath: "/inventory", smokeFlow: "inventory-list-loads" },
  { flag: "knowledge", owner: "knowledge", smokePath: "/knowledge", smokeFlow: "knowledge-search-loads" },
  { flag: "oa", owner: "workflow", smokePath: "/oa", smokeFlow: "oa-center-loads" },
  { flag: "plugins", owner: "platform", smokePath: "/plugins", smokeFlow: "plugin-install-flow-loads" },
  { flag: "projects", owner: "delivery", smokePath: "/projects", smokeFlow: "project-list-loads" },
  { flag: "report_builder", owner: "analytics", smokePath: "/report-builder", smokeFlow: "report-builder-loads" },
  { flag: "reports", owner: "analytics", smokePath: "/reports", smokeFlow: "reports-dashboard-loads" },
  { flag: "sales", owner: "sales", smokePath: "/sales", smokeFlow: "sales-pipeline-loads" },
  { flag: "soul_document", owner: "knowledge", smokePath: "/soul-document", smokeFlow: "soul-document-loads" },
  { flag: "tender", owner: "sales", smokePath: "/tender-analysis", smokeFlow: "tender-analysis-loads" },
  { flag: "training", owner: "people", smokePath: "/training", smokeFlow: "training-center-loads" },
  { flag: "vmd", owner: "marketing", smokePath: "/vmd", smokeFlow: "vmd-center-loads" },
  { flag: "workflow_designer", owner: "workflow", smokePath: "/workflows", smokeFlow: "workflow-list-loads" },
  { flag: "work_orders", owner: "support", smokePath: "/work-orders", smokeFlow: "work-order-list-loads" },
];

export const CUSTOMER_LAUNCH_MODULE_READINESS = ALL_CUSTOMER_LAUNCH_MODULE_READINESS.filter(
  (module) => CUSTOMER_LAUNCH_ENABLED_MODULES.includes(module.flag),
);

export const CUSTOMER_LAUNCH_SMOKE_PATHS = CUSTOMER_LAUNCH_MODULE_READINESS.map(
  (module) => module.smokePath,
);

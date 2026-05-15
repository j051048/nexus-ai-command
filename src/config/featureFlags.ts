export type ModuleFlag =
  | "approval"
  | "assets"
  | "battlecards"
  | "billing"
  | "certificates"
  | "crm"
  | "custom_dashboard"
  | "dev_tools"
  | "documents"
  | "finance"
  | "form_designer"
  | "hr"
  | "import"
  | "inventory"
  | "knowledge"
  | "oa"
  | "plugins"
  | "projects"
  | "report_builder"
  | "reports"
  | "sales"
  | "soul_document"
  | "tender"
  | "training"
  | "vmd"
  | "workflow_designer"
  | "work_orders";

export const SMALL_COMPANY_LAUNCH_MODULES: ModuleFlag[] = [
  "approval",
  "crm",
  "documents",
  "finance",
  "hr",
  "knowledge",
  "oa",
  "plugins",
  "projects",
  "reports",
  "vmd",
  "workflow_designer",
];

export const EXTENDED_LAUNCH_MODULES: ModuleFlag[] = [
  "approval",
  "assets",
  "battlecards",
  "billing",
  "certificates",
  "crm",
  "custom_dashboard",
  "documents",
  "finance",
  "form_designer",
  "hr",
  "import",
  "inventory",
  "knowledge",
  "oa",
  "plugins",
  "projects",
  "report_builder",
  "reports",
  "sales",
  "soul_document",
  "tender",
  "training",
  "vmd",
  "workflow_designer",
  "work_orders",
];

const launchProfile = String(import.meta.env.VITE_LAUNCH_PROFILE || "small_company").toLowerCase();

export const CUSTOMER_LAUNCH_ENABLED_MODULES: ModuleFlag[] =
  launchProfile === "extended" ? EXTENDED_LAUNCH_MODULES : SMALL_COMPANY_LAUNCH_MODULES;

export const CUSTOMER_LAUNCH_DISABLED_MODULES: ModuleFlag[] = [
  "dev_tools",
];

const DEFAULT_ENABLED: Set<ModuleFlag> = new Set(CUSTOMER_LAUNCH_ENABLED_MODULES);

function parseList(value: unknown): Set<string> {
  if (typeof value !== "string" || value.trim() === "") return new Set();
  return new Set(
    value
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean),
  );
}

const enabledOverride = parseList(import.meta.env.VITE_ENABLED_MODULES);
const disabledOverride = parseList(import.meta.env.VITE_DISABLED_MODULES);

export function isModuleEnabled(flag: ModuleFlag): boolean {
  if (disabledOverride.has(flag)) return false;
  if (enabledOverride.size > 0) return enabledOverride.has(flag);
  return DEFAULT_ENABLED.has(flag);
}

export function getEnabledModules(): ModuleFlag[] {
  return Array.from(DEFAULT_ENABLED).filter(isModuleEnabled);
}

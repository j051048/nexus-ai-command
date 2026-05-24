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

export type ModuleTier = "core" | "specialized" | "integration";

export const MODULE_TIER_LABELS: Record<ModuleTier, string> = {
  core: "核心场景",
  specialized: "专业场景",
  integration: "外部系统/低频",
};

export const MODULE_TIER_DESCRIPTIONS: Record<ModuleTier, string> = {
  core: "默认打磨到首发可用，承载每日高频工作。",
  specialized: "按客户行业和团队成熟度开启，服务差异化业务。",
  integration: "优先通过第三方集成承接，产品内保留轻入口。",
};

export const MODULE_TIERS: Record<ModuleTier, ModuleFlag[]> = {
  core: [
    "approval",
    "crm",
    "documents",
    "knowledge",
    "projects",
    "reports",
    "sales",
    "workflow_designer",
  ],
  specialized: [
    "battlecards",
    "custom_dashboard",
    "form_designer",
    "plugins",
    "report_builder",
    "soul_document",
    "tender",
    "training",
    "vmd",
    "work_orders",
  ],
  integration: [
    "assets",
    "billing",
    "certificates",
    "finance",
    "hr",
    "import",
    "inventory",
    "oa",
  ],
};

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

export function getModuleTier(flag: ModuleFlag): ModuleTier {
  for (const [tier, modules] of Object.entries(MODULE_TIERS) as Array<
    [ModuleTier, ModuleFlag[]]
  >) {
    if (modules.includes(flag)) return tier;
  }
  return "specialized";
}

export function getEnabledModulesByTier(tier: ModuleTier): ModuleFlag[] {
  return MODULE_TIERS[tier].filter(isModuleEnabled);
}

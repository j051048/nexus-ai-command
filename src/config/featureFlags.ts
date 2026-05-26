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

export const CORE_NATIVE_MODULES: ModuleFlag[] = MODULE_TIERS.core;
export const SPECIALIZED_AI_NATIVE_MODULES: ModuleFlag[] = [
  "battlecards",
  "tender",
  "vmd",
  "knowledge",
  "crm",
];
export const THIRD_PARTY_FIRST_MODULES: ModuleFlag[] = [
  "finance",
  "hr",
  "inventory",
  "oa",
  "billing",
];

export const MODULE_FOCUS_POLICY = {
  defaultNavigation: "five-space-workbench",
  superScenario: "VMD + scientific-instrument sales intelligence",
  nativeDepthRule: "Build deep native UX only for core sales, approval, knowledge, reports, and VMD scenarios.",
  integrationRule: "Keep HR, finance, OA, inventory, and billing as light entry points unless a customer explicitly enables deep native workflows.",
} as const;

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

export type IntegrationStrategyStatus = "native_core" | "light_entry" | "third_party_first";

export interface ModuleIntegrationStrategy {
  flag: ModuleFlag;
  status: IntegrationStrategyStatus;
  owner: string;
  recommendedVendors: string[];
  productDecision: string;
}

export const MODULE_INTEGRATION_STRATEGY: ModuleIntegrationStrategy[] = [
  {
    flag: "crm",
    status: "native_core",
    owner: "sales-product",
    recommendedVendors: [],
    productDecision: "作为科学仪器销售主战场继续深挖，客户 360、行动台和行业知识优先内建。",
  },
  {
    flag: "approval",
    status: "native_core",
    owner: "workflow-product",
    recommendedVendors: [],
    productDecision: "保留原生审批与行动台 inline approval，承载 AI 风控和业务闭环。",
  },
  {
    flag: "hr",
    status: "third_party_first",
    owner: "platform-integrations",
    recommendedVendors: ["飞书人事", "钉钉人事", "企业微信通讯录"],
    productDecision: "产品内仅保留员工与组织轻入口，深度人事流程优先对接第三方。",
  },
  {
    flag: "finance",
    status: "third_party_first",
    owner: "platform-integrations",
    recommendedVendors: ["金蝶", "用友", "Stripe"],
    productDecision: "费用与回款进入行动台，凭证、总账、税务和复杂财务流程交给专业系统。",
  },
  {
    flag: "oa",
    status: "light_entry",
    owner: "platform-integrations",
    recommendedVendors: ["飞书", "钉钉", "企业微信"],
    productDecision: "保留公告、通知和快捷入口；考勤、会议室、IM 工作流优先连接现有办公平台。",
  },
  {
    flag: "inventory",
    status: "third_party_first",
    owner: "platform-integrations",
    recommendedVendors: ["金蝶云星空", "用友 U8", "ERP"],
    productDecision: "库存只做销售/项目上下文引用，不在 Nexus 内重建完整 ERP。",
  },
];

export function getIntegrationStrategy(flag: ModuleFlag): ModuleIntegrationStrategy | undefined {
  return MODULE_INTEGRATION_STRATEGY.find((item) => item.flag === flag);
}

export function isThirdPartyFirstModule(flag: ModuleFlag): boolean {
  return THIRD_PARTY_FIRST_MODULES.includes(flag);
}

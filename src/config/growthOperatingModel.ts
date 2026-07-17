import {
  BarChart3,
  Building2,
  Crosshair,
  FileSearch,
  Radar,
  type LucideIcon,
} from "lucide-react";

export const GROWTH_OPERATING_MODEL_VERSION = "growth-command.v1";

export type GrowthWorkspaceView = "today" | "radar" | "accounts" | "tenders" | "review";

export interface GrowthWorkspaceRoute {
  key: GrowthWorkspaceView;
  label: string;
  shortLabel: string;
  path: string;
  icon: LucideIcon;
  purpose: string;
}

export const GROWTH_WORKSPACE_ROUTES: GrowthWorkspaceRoute[] = [
  {
    key: "today",
    label: "今日作战",
    shortLabel: "今日",
    path: "/dashboard",
    icon: Crosshair,
    purpose: "把最值得处理的机会、风险和节点排成行动队列",
  },
  {
    key: "radar",
    label: "线索雷达",
    shortLabel: "雷达",
    path: "/growth/radar",
    icon: Radar,
    purpose: "聚合行业线索、客户停滞与投标节点",
  },
  {
    key: "accounts",
    label: "客户与项目",
    shortLabel: "客户",
    path: "/growth/accounts",
    icon: Building2,
    purpose: "围绕下一步推进客户，而不是维护静态档案",
  },
  {
    key: "tenders",
    label: "投标作战",
    shortLabel: "投标",
    path: "/growth/tenders",
    icon: FileSearch,
    purpose: "提前暴露资格、技术与商务缺口",
  },
  {
    key: "review",
    label: "经营复盘",
    shortLabel: "复盘",
    path: "/growth/review",
    icon: BarChart3,
    purpose: "用行动采纳、完成和业务结果证明 AI 价值",
  },
];

export const INDUSTRY_CATEGORY_SLOTS = [
  "质谱与色谱",
  "光谱与波谱",
  "显微与成像",
  "材料表征",
  "生命科学仪器",
] as const;

export const GROWTH_EXTENSION_CONTRACTS = {
  signalProvider: "GrowthCapabilityProvider",
  actionPolicy: "risk_level + requires_confirmation",
  playbook: "agents + acceptance + risk_policy",
  outcomeEvidence: "growth_outcome_events",
  schemaVersion: GROWTH_OPERATING_MODEL_VERSION,
} as const;

export function viewFromPath(pathname: string): GrowthWorkspaceView {
  if (pathname.includes("/growth/radar")) return "radar";
  if (pathname.includes("/growth/accounts")) return "accounts";
  if (pathname.includes("/growth/tenders")) return "tenders";
  if (pathname.includes("/growth/review")) return "review";
  return "today";
}

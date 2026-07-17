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

export const SCIENTIFIC_INSTRUMENT_LINES = [
  {
    code: "spectroscopy",
    name: "光谱",
    description: "元素、分子结构与材料光学响应分析",
    families: ["原子吸收", "ICP-OES", "紫外可见", "红外", "拉曼", "荧光光谱"],
  },
  {
    code: "chromatography",
    name: "色谱",
    description: "复杂混合物分离、定量与纯度分析",
    families: ["气相色谱", "液相色谱", "离子色谱", "凝胶色谱", "制备色谱"],
  },
  {
    code: "mass_spectrometry",
    name: "质谱",
    description: "高灵敏定性、定量与结构解析",
    families: ["GC-MS", "LC-MS", "ICP-MS", "MALDI-TOF", "高分辨质谱"],
  },
  {
    code: "energy_spectroscopy",
    name: "能谱",
    description: "元素组成、表面化学与失效分析",
    families: ["EDS/EDX", "XRF", "XPS", "AES", "电子能量损失谱"],
  },
  {
    code: "electronic_instrumentation",
    name: "电子仪器",
    description: "电子、通信、半导体与先进制造测试",
    families: ["示波器", "频谱分析仪", "网络分析仪", "信号源", "半导体测试", "自动化测试系统"],
  },
] as const;

export type InstrumentLineCode = (typeof SCIENTIFIC_INSTRUMENT_LINES)[number]["code"];

export const INDUSTRY_CATEGORY_SLOTS = SCIENTIFIC_INSTRUMENT_LINES.map(
  (line) => line.name,
);

export function getInstrumentLine(code?: string | null) {
  return SCIENTIFIC_INSTRUMENT_LINES.find((line) => line.code === code);
}

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

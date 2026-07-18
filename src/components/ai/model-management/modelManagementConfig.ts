import { Crown, Leaf, Rocket, Zap } from "lucide-react";

import type { LLMModel } from "@/hooks/useVMD";

export const MODEL_PROVIDERS = [
  { value: "openai", label: "OpenAI兼容" },
  { value: "baidu", label: "百度文心" },
  { value: "aliyun", label: "阿里通义" },
  { value: "tencent", label: "腾讯混元" },
  { value: "bytedance", label: "字节豆包" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "yi", label: "零一万物" },
  { value: "anthropic", label: "Anthropic" },
] as const;

export const MODEL_PROVIDER_NAMES: Record<string, string> = Object.fromEntries(
  MODEL_PROVIDERS.map((provider) => [provider.value, provider.label]),
);

export const MODEL_TIERS = [
  {
    value: "economy",
    label: "经济层",
    icon: Leaf,
    color: "text-green-600",
    bgColor: "bg-green-50 dark:bg-green-950/30",
    description: "简单问候、FAQ — 低成本高速响应",
  },
  {
    value: "balanced",
    label: "均衡层",
    icon: Zap,
    color: "text-blue-600",
    bgColor: "bg-blue-50 dark:bg-blue-950/30",
    description: "单工具查询、状态查看 — 兼顾成本与能力",
  },
  {
    value: "power",
    label: "强力层",
    icon: Rocket,
    color: "text-orange-600",
    bgColor: "bg-orange-50 dark:bg-orange-950/30",
    description: "多步分析、报告生成 — 高级推理能力",
  },
  {
    value: "flagship",
    label: "旗舰层",
    icon: Crown,
    color: "text-purple-600",
    bgColor: "bg-purple-50 dark:bg-purple-950/30",
    description: "审批、财务操作 — 最高准确性保证",
  },
] as const;

export const EMPTY_MODEL: Partial<LLMModel> = {
  provider_type: "openai",
  model_code: "",
  model_name: "",
  api_base_url: "",
  api_key: "",
  secret_key: "",
  model_id: "",
  model_type: "chat",
  timeout_ms: 30000,
  max_tokens: 4096,
  context_window: 8192,
  supports_tools: true,
  supports_streaming: true,
  input_price: 0,
  output_price: 0,
  is_active: true,
  is_default: false,
};

export const MODEL_TAG_COLORS: Record<string, string> = {
  推荐: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
  高性价比: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20",
  多模态: "bg-violet-500/15 text-violet-700 dark:text-violet-400 border-violet-500/20",
  深度推理: "bg-orange-500/15 text-orange-700 dark:text-orange-400 border-orange-500/20",
  推理: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20",
  国产: "bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/20",
  超长上下文: "bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 border-cyan-500/20",
  长上下文: "bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 border-cyan-500/20",
  经济: "bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/20",
  开源: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-400 border-indigo-500/20",
  向量: "bg-purple-500/15 text-purple-700 dark:text-purple-400 border-purple-500/20",
  免费: "bg-lime-500/15 text-lime-700 dark:text-lime-400 border-lime-500/20",
  最新: "bg-pink-500/15 text-pink-700 dark:text-pink-400 border-pink-500/20",
  最强推理: "bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20",
  实验: "bg-gray-500/15 text-gray-700 dark:text-gray-400 border-gray-500/20",
};

export function formatContextWindow(value: number): string {
  if (!value) return "-";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1000) return `${Math.round(value / 1000)}K`;
  return String(value);
}

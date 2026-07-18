import type { ElementType } from "react";
import { Bot, CheckCircle2, Clock, Eye, Play, XCircle } from "lucide-react";

import { SCENES } from "@/components/vmd/SceneSelector";

export const VMD_TASK_STATUS_CONFIG: Record<
  string,
  { label: string; color: string; icon: ElementType }
> = {
  planning: {
    label: "规划中",
    color: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    icon: Bot,
  },
  pending: {
    label: "待处理",
    color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    icon: Clock,
  },
  executing: {
    label: "执行中",
    color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    icon: Play,
  },
  reviewing: {
    label: "审核中",
    color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    icon: Eye,
  },
  done: {
    label: "已完成",
    color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    icon: CheckCircle2,
  },
  failed: {
    label: "失败",
    color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    icon: XCircle,
  },
};

export const VMD_TASK_PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: {
    label: "低",
    color: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  },
  normal: {
    label: "普通",
    color: "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400",
  },
  high: {
    label: "高",
    color: "bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-400",
  },
  urgent: {
    label: "紧急",
    color: "bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-400",
  },
};

export const VMD_SCENE_NAMES: Record<string, string> = Object.fromEntries(
  SCENES.map((scene) => [scene.code, scene.name]),
);

import { useEffect, useMemo, useState } from "react";
import type { ComponentType } from "react";
import { Link } from "react-router-dom";
import {
  Bot,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  Upload,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type LaunchChecklistPanelProps = {
  role?: "boss" | "founder" | "manager" | "employee" | string | null;
  compact?: boolean;
};

type LaunchTask = {
  id: string;
  title: string;
  description: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  roles?: string[];
};

const TASKS: LaunchTask[] = [
  {
    id: "company_profile",
    title: "完善公司与组织信息",
    description: "确认公司名称、部门、角色和审批负责人。",
    href: "/company-settings",
    icon: Building2,
    roles: ["boss", "founder", "manager"],
  },
  {
    id: "invite_team",
    title: "邀请核心成员",
    description: "先邀请老板、财务、人事、销售和项目负责人。",
    href: "/org-chart",
    icon: Users,
    roles: ["boss", "founder", "manager"],
  },
  {
    id: "crm_first_customer",
    title: "创建第一个客户",
    description: "让销售团队从真实客户开始试跑。",
    href: "/crm",
    icon: ClipboardCheck,
  },
  {
    id: "approval_first_request",
    title: "发起一次审批",
    description: "跑通请假、报销或采购审批闭环。",
    href: "/approval",
    icon: CheckCircle2,
  },
  {
    id: "upload_document",
    title: "上传业务文档",
    description: "把制度、报价单、合同模板放进知识库。",
    href: "/documents",
    icon: Upload,
  },
  {
    id: "ask_ai",
    title: "问 AI 一个公司问题",
    description: "验证 AI 是否能解释数据来源和下一步动作。",
    href: "/dashboard#ai-chat",
    icon: Bot,
  },
  {
    id: "handoff_ready",
    title: "检查上线交付状态",
    description: "管理员确认健康检查、证据包和验收命令。",
    href: "/deployment-readiness",
    icon: FileText,
    roles: ["boss", "founder"],
  },
];

const STORAGE_KEY = "nexus:first-week-launch-checklist";

function loadCompleted(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function saveCompleted(value: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(value)));
}

export function LaunchChecklistPanel({ role, compact = false }: LaunchChecklistPanelProps) {
  const [completed, setCompleted] = useState<Set<string>>(loadCompleted);

  useEffect(() => {
    saveCompleted(completed);
  }, [completed]);

  const tasks = useMemo(() => {
    const currentRole = role || "employee";
    return TASKS.filter((task) => !task.roles || task.roles.includes(currentRole));
  }, [role]);

  const doneCount = tasks.filter((task) => completed.has(task.id)).length;
  const progress = tasks.length ? Math.round((doneCount / tasks.length) * 100) : 0;

  const toggle = (id: string) => {
    setCompleted((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <Card>
      <CardHeader className={cn("pb-3", compact && "pb-2")}>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="text-base">首周落地任务</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              按这几步跑通，公司就能从演示进入真实使用。
            </p>
          </div>
          <div className="text-sm font-medium text-muted-foreground">{progress}% 完成</div>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress}%` }} />
        </div>
      </CardHeader>
      <CardContent className={cn("grid gap-2", compact ? "md:grid-cols-2" : "lg:grid-cols-2")}>
        {tasks.map((task) => {
          const Icon = task.icon;
          const checked = completed.has(task.id);
          return (
            <div
              key={task.id}
              className={cn(
                "flex items-start gap-3 rounded-lg border bg-card p-3 transition-colors",
                checked && "border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/20",
              )}
            >
              <button
                type="button"
                aria-label={checked ? "标记为未完成" : "标记为完成"}
                onClick={() => toggle(task.id)}
                className={cn(
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
                  checked ? "border-emerald-500 bg-emerald-500 text-white" : "border-muted-foreground/30",
                )}
              >
                {checked && <CheckCircle2 className="h-4 w-4" />}
              </button>
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{task.title}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">{task.description}</div>
                <Button asChild variant="link" size="sm" className="mt-1 h-auto p-0 text-xs">
                  <Link to={task.href}>去完成</Link>
                </Button>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export default LaunchChecklistPanel;

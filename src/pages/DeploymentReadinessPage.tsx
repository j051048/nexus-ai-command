import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  FileCheck2,
  RefreshCw,
  Server,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { httpClient } from "@/lib/httpClient";
import { cn } from "@/lib/utils";

type DeploymentCheck = {
  name: string;
  ok: boolean;
  value?: string | boolean;
  severity?: "critical" | "warning";
  message?: string;
};

type DeploymentHealth = {
  ready: boolean;
  environment: string;
  checks: DeploymentCheck[];
  warnings: DeploymentCheck[];
  summary: {
    critical_failed: number;
    warning_failed: number;
    production_mode: boolean;
  };
};

type ApiResponse<T> = { success: boolean; data: T };

const ACCEPTANCE_COMMANDS = [
  "python scripts/customer_acceptance_gate.py",
  "python scripts/release_quality_gate.py",
  "node scripts/production_readiness_check.mjs --env .env.production",
  "node scripts/production_health_check.mjs --base-url https://YOUR-BACKEND-DOMAIN",
  "python scripts/collect_release_evidence.py",
  "python scripts/collect_soc2_evidence.py",
  "python scripts/agent_replay_nightly.py",
  "npm run build",
  "npm run check:bundle",
  "npm run test:e2e -- e2e/customer-business-acceptance.spec.ts --project=chromium",
];

const HANDOFF_ARTIFACTS = [
  "dist/release-evidence.json",
  "dist/soc2-evidence.json",
  "dist/customer-handoff.md",
  "RLS scanner output",
  "Small-company k6 result",
  "Backup and restore drill result",
];

const PRODUCT_ACCEPTANCE = [
  "老板能从总控中心看到待批、异常、AI ROI 和上线交付状态",
  "员工能从工作台完成客户、审批、文档和 AI 问答首周任务",
  "管理员能解释权限矩阵、AI 工具边界和不可逆操作确认",
  "交付经理能导出 release/SOC2 证据并跑通小公司压测 profile",
];

export default function DeploymentReadinessPage() {
  const [data, setData] = useState<DeploymentHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await httpClient.get<ApiResponse<DeploymentHealth>>(
        "/api/system/deployment-health",
      );
      setData(response.data.data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "部署健康检查加载失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const allChecks = useMemo(
    () => [...(data?.checks || []), ...(data?.warnings || [])],
    [data],
  );
  const readyScore = useMemo(() => {
    if (!allChecks.length) return 0;
    return Math.round((allChecks.filter((item) => item.ok).length / allChecks.length) * 100);
  }, [allChecks]);

  const copyCommands = async () => {
    try {
      await navigator.clipboard.writeText(ACCEPTANCE_COMMANDS.join("\n"));
      toast.success("验收命令已复制");
    } catch {
      toast.error("浏览器不允许复制，请手动选择命令");
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal">上线交付中心</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            面向 20-50 人客户试点的部署健康、验收命令、证据包和运维交付清单。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={copyCommands}>
            <Clipboard className="mr-2 h-4 w-4" />
            复制验收命令
          </Button>
          <Button onClick={refresh} disabled={loading}>
            <RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />
            刷新健康状态
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard
          icon={<Server className="h-5 w-5" />}
          label="部署状态"
          value={data?.ready ? "Ready" : data ? "Blocked" : "--"}
          tone={data?.ready ? "good" : "bad"}
        />
        <MetricCard
          icon={<Activity className="h-5 w-5" />}
          label="就绪评分"
          value={`${readyScore}%`}
          tone={readyScore >= 90 ? "good" : readyScore >= 70 ? "warn" : "bad"}
        />
        <MetricCard
          icon={<AlertTriangle className="h-5 w-5" />}
          label="关键失败"
          value={String(data?.summary.critical_failed ?? "--")}
          tone={(data?.summary.critical_failed ?? 1) === 0 ? "good" : "bad"}
        />
        <MetricCard
          icon={<ShieldCheck className="h-5 w-5" />}
          label="生产模式"
          value={data?.summary.production_mode ? "Production" : data ? "Non-prod" : "--"}
          tone={data?.summary.production_mode ? "good" : "warn"}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">部署健康检查</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {allChecks.length === 0 ? (
              <div className="rounded-md bg-muted/40 p-4 text-sm text-muted-foreground">
                暂无健康数据。确认后端已注册 `/api/system/deployment-health`，且当前账号具备管理员权限。
              </div>
            ) : (
              allChecks.map((check) => <CheckRow key={`${check.name}-${check.severity}`} check={check} />)
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <TerminalSquare className="h-4 w-4" />
                必跑验收命令
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {ACCEPTANCE_COMMANDS.map((command) => (
                <code
                  key={command}
                  className="block rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground"
                >
                  {command}
                </code>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileCheck2 className="h-4 w-4" />
                客户交付证据
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {HANDOFF_ARTIFACTS.map((artifact) => (
                <div
                  key={artifact}
                  className="flex items-center justify-between gap-3 rounded-md bg-muted/40 px-3 py-2 text-sm"
                >
                  <span className="truncate">{artifact}</span>
                  <Badge variant="outline">handoff</Badge>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <CheckCircle2 className="h-4 w-4" />
                产品验收口径
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {PRODUCT_ACCEPTANCE.map((item) => (
                <div key={item} className="rounded-md bg-muted/40 px-3 py-2 text-sm">
                  {item}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone: "good" | "warn" | "bad";
}) {
  return (
    <Card>
      <CardContent className="flex h-28 flex-col justify-between p-4">
        <div className="flex items-center justify-between text-muted-foreground">
          <span className="text-sm">{label}</span>
          {icon}
        </div>
        <div
          className={cn(
            "text-2xl font-semibold tracking-normal",
            tone === "good" && "text-emerald-600",
            tone === "warn" && "text-amber-600",
            tone === "bad" && "text-destructive",
          )}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function CheckRow({ check }: { check: DeploymentCheck }) {
  return (
    <div className="flex flex-col gap-2 rounded-md border bg-card px-3 py-3 md:flex-row md:items-center md:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        {check.ok ? (
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
        ) : (
          <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
        )}
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{check.name}</div>
          {check.message && <div className="text-xs text-muted-foreground">{check.message}</div>}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Badge variant={check.ok ? "outline" : "destructive"}>
          {check.ok ? "ok" : check.severity || "failed"}
        </Badge>
        {typeof check.value !== "undefined" && (
          <span className="max-w-[220px] truncate text-xs text-muted-foreground">
            {String(check.value)}
          </span>
        )}
      </div>
    </div>
  );
}

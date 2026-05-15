import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Activity, Gauge, ShieldCheck, Timer } from "lucide-react";

import { httpClient } from "@/lib/httpClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type SLOData = {
  targets: {
    ai_response_p95_ms: number;
    api_response_p99_ms: number;
    availability_target: number;
    error_budget_window_days: number;
  };
  agent: {
    total_requests: number;
    error_count: number;
    success_rate: number;
    avg_response_time_ms: number;
    total_tokens: number;
    total_cost: number;
  };
  web_vitals: Record<string, { value: number; rating: string; path: string }>;
};

type ApiResponse<T> = { success: boolean; data: T };

export default function SLODashboard() {
  const [data, setData] = useState<SLOData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    httpClient
      .get<ApiResponse<SLOData>>("/api/metrics/slo")
      .then((response) => {
        if (mounted) setData(response.data.data);
      })
      .catch((err) => {
        if (mounted) setError(err instanceof Error ? err.message : "加载失败");
      });
    return () => {
      mounted = false;
    };
  }, []);

  const successRate = data ? `${(data.agent.success_rate * 100).toFixed(1)}%` : "--";
  const vitals = data ? Object.values(data.web_vitals || {}) : [];

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-normal">SLO Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">Agent latency, success rate, cost and Web Vitals.</p>
      </div>

      {error && <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">{error}</div>}

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard icon={<ShieldCheck className="h-4 w-4" />} label="Success Rate" value={successRate} />
        <MetricCard icon={<Timer className="h-4 w-4" />} label="Avg Agent Latency" value={`${data?.agent.avg_response_time_ms ?? "--"} ms`} />
        <MetricCard icon={<Activity className="h-4 w-4" />} label="Total Requests" value={String(data?.agent.total_requests ?? "--")} />
        <MetricCard icon={<Gauge className="h-4 w-4" />} label="Total Cost" value={`$${(data?.agent.total_cost ?? 0).toFixed(4)}`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Targets</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <Row label="AI P95" value={`${data?.targets.ai_response_p95_ms ?? "--"} ms`} />
            <Row label="API P99" value={`${data?.targets.api_response_p99_ms ?? "--"} ms`} />
            <Row label="Availability" value={`${data?.targets.availability_target ?? "--"}%`} />
            <Row label="Error Budget Window" value={`${data?.targets.error_budget_window_days ?? "--"} days`} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Core Web Vitals</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {vitals.length === 0 ? (
              <div className="text-muted-foreground">No browser vitals recorded yet.</div>
            ) : (
              vitals.map((vital) => (
                <Row
                  key={`${vital.path}-${vital.rating}-${vital.value}`}
                  label={`${vital.path} · ${vital.rating}`}
                  value={String(vital.value)}
                />
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <Card>
      <CardContent className="flex h-28 flex-col justify-between p-4">
        <div className="flex items-center justify-between text-muted-foreground">
          <span className="text-sm">{label}</span>
          {icon}
        </div>
        <div className="text-2xl font-semibold tracking-normal">{value}</div>
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md bg-muted/40 px-3 py-2">
      <span className="truncate text-muted-foreground">{label}</span>
      <span className="shrink-0 font-medium">{value}</span>
    </div>
  );
}

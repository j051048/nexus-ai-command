import { useState } from "react";
import { useRoiData } from "@/hooks/useRoiData";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, TrendingUp, Clock, DollarSign, Zap, ThumbsUp, ThumbsDown } from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const CATEGORY_LABELS: Record<string, string> = {
  approval: "审批",
  crm: "客户管理",
  report: "报告生成",
  attendance: "考勤",
  finance: "财务",
  leave: "请假",
  schedule: "日程",
  knowledge: "知识库",
  other: "其他",
};

const PIE_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#84cc16", "#6b7280",
];

export default function AiRoiDashboard() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useRoiData(days);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-96 text-muted-foreground">
        ROI 数据加载失败
      </div>
    );
  }

  const { summary, daily, by_category } = data;

  // Pie chart data
  const pieData = Object.entries(by_category)
    .filter(([, v]) => v > 0)
    .map(([key, value]) => ({
      name: CATEGORY_LABELS[key] || key,
      value,
    }))
    .sort((a, b) => b.value - a.value);

  const totalFeedback = summary.total_positive_feedback + summary.total_negative_feedback;
  const satisfactionRate = totalFeedback > 0
    ? Math.round((summary.total_positive_feedback / totalFeedback) * 100)
    : 0;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">AI 投资回报率</h1>
          <p className="text-muted-foreground text-sm mt-1">
            衡量 AI 为企业节省的时间和成本
          </p>
        </div>
        <Tabs value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <TabsList>
            <TabsTrigger value="7">7 天</TabsTrigger>
            <TabsTrigger value="30">30 天</TabsTrigger>
            <TabsTrigger value="90">90 天</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              ROI
            </CardTitle>
            <TrendingUp className="w-4 h-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-600">
              {summary.avg_roi_percent > 9000
                ? "∞"
                : `${summary.avg_roi_percent.toLocaleString()}%`}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              AI 成本 ${summary.total_ai_cost.toFixed(2)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              节省时间
            </CardTitle>
            <Clock className="w-4 h-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-blue-600">
              {summary.total_minutes_saved >= 60
                ? `${(summary.total_minutes_saved / 60).toFixed(1)}h`
                : `${summary.total_minutes_saved.toFixed(0)}min`}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              相当于 {(summary.total_minutes_saved / 480).toFixed(1)} 个工作日
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              节省成本
            </CardTitle>
            <DollarSign className="w-4 h-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-emerald-600">
              ${summary.total_labor_saved.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              人工等价成本估算
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              AI 执行量
            </CardTitle>
            <Zap className="w-4 h-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-amber-600">
              {summary.total_tool_calls.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              成功率{" "}
              {summary.total_tool_calls > 0
                ? Math.round(
                    (summary.total_tool_success / summary.total_tool_calls) * 100
                  )
                : 0}
              % | LLM 调用 {summary.total_llm_calls.toLocaleString()} 次
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ROI Trend Area Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">ROI 趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(v) => v.slice(5)}
                  fontSize={12}
                />
                <YAxis fontSize={12} />
                <Tooltip
                  formatter={(value: number, name: string) => [
                    name === "saved" || name === "cost"
                      ? `$${value.toFixed(2)}`
                      : value.toFixed(1),
                    name === "saved"
                      ? "节省成本"
                      : name === "cost"
                      ? "AI 成本"
                      : "ROI %",
                  ]}
                  labelFormatter={(label) => `日期: ${label}`}
                />
                <Legend
                  formatter={(value) =>
                    value === "saved"
                      ? "节省成本"
                      : value === "cost"
                      ? "AI 成本"
                      : "ROI %"
                  }
                />
                <Area
                  type="monotone"
                  dataKey="saved"
                  stroke="#10b981"
                  fill="#10b98133"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="cost"
                  stroke="#ef4444"
                  fill="#ef444433"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Category Pie Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">操作分类</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, percent }) =>
                    `${name} ${(percent * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {pieData.map((_, index) => (
                    <Cell
                      key={index}
                      fill={PIE_COLORS[index % PIE_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Tool Calls Bar Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">每日操作量</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(v) => v.slice(5)}
                  fontSize={12}
                />
                <YAxis fontSize={12} />
                <Tooltip
                  formatter={(value: number) => [value, "工具调用"]}
                  labelFormatter={(label) => `日期: ${label}`}
                />
                <Bar
                  dataKey="tool_calls"
                  fill="#3b82f6"
                  radius={[4, 4, 0, 0]}
                  name="工具调用"
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Satisfaction & Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">服务质量</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">用户满意度</span>
              <span className="text-2xl font-bold">
                {satisfactionRate}%
              </span>
            </div>
            <div className="flex gap-6">
              <div className="flex items-center gap-2 text-green-600">
                <ThumbsUp className="w-4 h-4" />
                <span className="text-sm font-medium">
                  {summary.total_positive_feedback}
                </span>
              </div>
              <div className="flex items-center gap-2 text-red-500">
                <ThumbsDown className="w-4 h-4" />
                <span className="text-sm font-medium">
                  {summary.total_negative_feedback}
                </span>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  平均响应时间
                </span>
                <span className="font-medium">
                  {summary.avg_response_time_ms > 1000
                    ? `${(summary.avg_response_time_ms / 1000).toFixed(1)}s`
                    : `${summary.avg_response_time_ms}ms`}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  总 Token 消耗
                </span>
                <span className="font-medium">
                  {summary.total_tokens > 1000000
                    ? `${(summary.total_tokens / 1000000).toFixed(1)}M`
                    : `${(summary.total_tokens / 1000).toFixed(0)}K`}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  工具成功率
                </span>
                <span className="font-medium">
                  {summary.total_tool_calls > 0
                    ? `${Math.round(
                        (summary.total_tool_success / summary.total_tool_calls) *
                          100
                      )}%`
                    : "N/A"}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

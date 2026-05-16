import { Link } from "react-router-dom";
import { BarChart3, Bot, CheckCircle2, Clock, LineChart, Rocket, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SUCCESS_METRICS = [
  {
    label: "首周激活目标",
    value: "80%",
    hint: "核心员工至少登录并完成 1 个业务动作",
    icon: Users,
  },
  {
    label: "审批提速目标",
    value: "30%",
    hint: "请假、报销、采购流程平均处理时长下降",
    icon: Clock,
  },
  {
    label: "AI 使用目标",
    value: "5次/人",
    hint: "每位核心成员首周至少问 AI 5 次",
    icon: Bot,
  },
  {
    label: "老板复盘目标",
    value: "1次/周",
    hint: "用总控中心和 ROI 报表做周会复盘",
    icon: BarChart3,
  },
];

const PLAYBOOKS = [
  {
    title: "第 1 天：跑通基础资料",
    items: ["导入组织架构", "创建第一个客户", "上传制度/合同模板", "配置审批负责人"],
  },
  {
    title: "第 3 天：让团队开始用",
    items: ["员工发起审批", "销售更新客户", "项目负责人更新进度", "AI 回答知识库问题"],
  },
  {
    title: "第 7 天：给老板看价值",
    items: ["查看总控中心", "导出 AI ROI", "复盘审批提速", "决定是否打开扩展模块"],
  },
];

const VALUE_INDICATORS = [
  "审批平均处理时长变化",
  "CRM 客户跟进及时率",
  "知识库问答命中率和人工节省时间",
  "AI 成本 / 业务动作 / 员工活跃度趋势",
];

export default function CustomerSuccessPage() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal">客户成功看板</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            用一页讲清楚客户首周怎么用、怎么验收、怎么证明这套系统有价值。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline">
            <Link to="/deployment-readiness">查看交付状态</Link>
          </Button>
          <Button asChild>
            <Link to="/ai-roi">查看 AI ROI</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        {SUCCESS_METRICS.map((metric) => {
          const Icon = metric.icon;
          return (
            <Card key={metric.label}>
              <CardContent className="flex h-32 flex-col justify-between p-4">
                <div className="flex items-center justify-between text-muted-foreground">
                  <span className="text-sm">{metric.label}</span>
                  <Icon className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-2xl font-semibold tracking-normal">{metric.value}</div>
                  <p className="mt-1 text-xs text-muted-foreground">{metric.hint}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {PLAYBOOKS.map((playbook) => (
          <Card key={playbook.title}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Rocket className="h-4 w-4" />
                {playbook.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {playbook.items.map((item) => (
                <div key={item} className="flex items-center gap-3 rounded-md bg-muted/40 px-3 py-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                  <span>{item}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <LineChart className="h-4 w-4" />
            建议给客户汇报的 4 个价值指标
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {VALUE_INDICATORS.map((item) => (
            <div key={item} className="rounded-lg border bg-card px-4 py-3 text-sm">
              {item}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

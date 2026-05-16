import { CheckCircle2, Eye, Lock, ShieldCheck, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const ROLES = [
  {
    role: "founder / boss",
    label: "老板/创始人",
    access: ["总控中心", "审批", "财务", "AI 成本", "上线交付", "工具治理"],
    ai: "可使用高风险工具，但不可逆操作仍需要 HITL 确认。",
  },
  {
    role: "manager",
    label: "部门负责人",
    access: ["团队审批", "项目", "CRM", "报表", "部门数据"],
    ai: "可调用部门业务工具，跨部门敏感数据默认隔离。",
  },
  {
    role: "employee",
    label: "员工",
    access: ["个人工作台", "待办", "审批发起", "文档", "知识库"],
    ai: "默认只能执行本人或授权范围内的查询与低风险动作。",
  },
  {
    role: "ai_assistant",
    label: "AI 助手",
    access: ["工具调用", "知识检索", "流程辅助"],
    ai: "通过 Tool RBAC、Prompt Firewall、Token Budget 和审计日志约束。",
  },
];

const SAFETY_LAYERS = [
  "Supabase RLS 租户隔离",
  "Tool RBAC 默认拒绝与显式允许",
  "不可逆操作人工确认",
  "Prompt 注入与越权拦截",
  "LLM 成本与 Token 熔断",
  "不可篡改审计日志",
];

export default function PermissionMatrixPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-normal">权限与 AI 安全矩阵</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          给客户管理员解释清楚：谁能看什么、AI 能做什么、危险动作在哪里被拦住。
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        {ROLES.map((item) => (
          <Card key={item.role}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ShieldCheck className="h-4 w-4" />
                {item.label}
              </CardTitle>
              <Badge variant="outline" className="w-fit">
                {item.role}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div>
                <div className="mb-2 flex items-center gap-2 font-medium">
                  <Eye className="h-4 w-4 text-muted-foreground" />
                  可见范围
                </div>
                <div className="flex flex-wrap gap-2">
                  {item.access.map((entry) => (
                    <Badge key={entry} variant="secondary">
                      {entry}
                    </Badge>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 flex items-center gap-2 font-medium">
                  <Wrench className="h-4 w-4 text-muted-foreground" />
                  AI 行为边界
                </div>
                <p className="text-muted-foreground">{item.ai}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Lock className="h-4 w-4" />
            客户最关心的安全兜底
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {SAFETY_LAYERS.map((layer) => (
            <div key={layer} className="flex items-center gap-3 rounded-lg border bg-card px-3 py-3 text-sm">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
              <span>{layer}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

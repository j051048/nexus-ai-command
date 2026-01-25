import React from 'react';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Users,
  DollarSign,
  BarChart3,
  FileCheck,
  XCircle,
  ChevronRight,
  Bot,
} from 'lucide-react';

const weeklyReport = {
  cashFlow: 1250000,
  cashFlowTrend: 12.5,
  salesRisks: [
    '张教授商机超过30天未推进',
    '李博士报价已过期7天',
  ],
  totalIncentives: 28500,
  topPerformers: [
    { name: '王晓明', score: 95, bonus: 8200 },
    { name: '刘芳', score: 91, bonus: 6800 },
    { name: '张明', score: 87, bonus: 4850 },
  ],
};

const pendingExceptions = [
  {
    id: '1',
    type: 'purchase',
    title: '采购申请超预算',
    description: '示波器采购单超出预算10%，需确认',
    amount: 9900,
    budget: 9000,
    submitter: '陈伟',
    submittedAt: '2小时前',
    priority: 'high',
  },
  {
    id: '2',
    type: 'travel',
    title: '紧急出差申请',
    description: '客户临时要求现场演示，需加急审批',
    amount: 4500,
    budget: 3000,
    submitter: '李娜',
    submittedAt: '4小时前',
    priority: 'urgent',
  },
  {
    id: '3',
    type: 'expense',
    title: '报销单金额异常',
    description: '餐饮费用超出标准，AI建议人工复核',
    amount: 580,
    budget: 300,
    submitter: '张明',
    submittedAt: '1天前',
    priority: 'medium',
  },
];

const teamHeatmap = [
  { name: '王晓明', mon: 95, tue: 88, wed: 92, thu: 90, fri: 95 },
  { name: '刘芳', mon: 85, tue: 91, wed: 88, thu: 92, fri: 89 },
  { name: '张明', mon: 80, tue: 85, wed: 87, thu: 88, fri: 90 },
  { name: '陈伟', mon: 75, tue: 78, wed: 82, thu: 80, fri: 78 },
  { name: '李娜', mon: 70, tue: 75, wed: 78, thu: 76, fri: 80 },
];

const getHeatColor = (score: number) => {
  if (score >= 90) return 'bg-success';
  if (score >= 80) return 'bg-primary';
  if (score >= 70) return 'bg-warning';
  return 'bg-destructive';
};

export function BossDashboard() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">总控中心</h1>
          <p className="text-muted-foreground mt-1">
            早上好！今日仅有 <span className="text-warning font-semibold">3</span> 条异常需要您处理
          </p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-success/20 rounded-xl">
          <CheckCircle2 className="w-5 h-5 text-success" />
          <span className="text-success font-medium">95% 事务已由AI自动处理</span>
        </div>
      </div>

      {/* AI Weekly Report */}
      <div className="bg-gradient-card rounded-2xl p-6 cyber-border">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center">
            <Bot className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">AI 周报摘要</h2>
            <p className="text-xs text-muted-foreground">本周自动生成 · 数据截至今日 09:00</p>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-6">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">预计本周现金流</p>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-foreground mono-number">
                ¥{(weeklyReport.cashFlow / 10000).toFixed(0)}万
              </span>
              <span className="flex items-center text-success text-sm">
                <TrendingUp className="w-4 h-4" />
                {weeklyReport.cashFlowTrend}%
              </span>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">AI检测销售风险</p>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-warning mono-number">
                {weeklyReport.salesRisks.length}
              </span>
              <span className="text-sm text-muted-foreground">条待关注</span>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">本周自动激励发放</p>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-success mono-number">
                ¥{weeklyReport.totalIncentives.toLocaleString()}
              </span>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">AI审批处理率</p>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-primary mono-number">95%</span>
              <span className="text-sm text-muted-foreground">自动通过</span>
            </div>
          </div>
        </div>

        {/* Risk Alerts */}
        <div className="mt-6 p-4 bg-warning/10 rounded-xl border border-warning/30">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-warning" />
            <span className="text-sm font-medium text-warning">AI风险提醒</span>
          </div>
          <ul className="space-y-2">
            {weeklyReport.salesRisks.map((risk, index) => (
              <li key={index} className="text-sm text-muted-foreground flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-warning" />
                {risk}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Exception Queue */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-warning/20 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-warning" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">异常待办</h2>
              <p className="text-xs text-muted-foreground">仅显示AI无法自动处理的5%异常</p>
            </div>
          </div>
          <span className="text-sm text-muted-foreground">
            共 <span className="text-warning font-semibold">{pendingExceptions.length}</span> 条
          </span>
        </div>

        <div className="space-y-4">
          {pendingExceptions.map((item) => (
            <div
              key={item.id}
              className={cn(
                "p-4 rounded-xl border transition-colors hover:bg-secondary/50",
                item.priority === 'urgent' && "border-destructive/50 bg-destructive/5",
                item.priority === 'high' && "border-warning/50 bg-warning/5",
                item.priority === 'medium' && "border-border"
              )}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn(
                      "px-2 py-0.5 text-xs font-medium rounded-full",
                      item.priority === 'urgent' && "bg-destructive/20 text-destructive",
                      item.priority === 'high' && "bg-warning/20 text-warning",
                      item.priority === 'medium' && "bg-muted text-muted-foreground"
                    )}>
                      {item.priority === 'urgent' ? '紧急' : item.priority === 'high' ? '较高' : '一般'}
                    </span>
                    <h3 className="font-medium text-foreground">{item.title}</h3>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">{item.description}</p>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>申请人：{item.submitter}</span>
                    <span>金额：<span className="text-foreground font-medium">¥{item.amount}</span></span>
                    <span>预算：<span className={item.amount > item.budget ? 'text-warning' : 'text-foreground'}>¥{item.budget}</span></span>
                    <span>提交于 {item.submittedAt}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="px-4 py-2 rounded-lg bg-destructive/20 text-destructive text-sm font-medium hover:bg-destructive/30 transition-colors flex items-center gap-1">
                    <XCircle className="w-4 h-4" />
                    驳回
                  </button>
                  <button className="px-4 py-2 rounded-lg bg-success text-white text-sm font-medium hover:bg-success/90 transition-colors flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" />
                    批准
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Team Performance Heatmap */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-card rounded-2xl p-6 border border-border">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-foreground">团队绩效热力图</h2>
            <button className="text-xs text-primary hover:underline flex items-center gap-1">
              详细分析 <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          
          <div className="space-y-3">
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <div className="w-20" />
              <div className="flex-1 grid grid-cols-5 gap-2 text-center">
                <span>周一</span>
                <span>周二</span>
                <span>周三</span>
                <span>周四</span>
                <span>周五</span>
              </div>
            </div>
            {teamHeatmap.map((member) => (
              <div key={member.name} className="flex items-center gap-3">
                <div className="w-20 text-sm text-foreground truncate">{member.name}</div>
                <div className="flex-1 grid grid-cols-5 gap-2">
                  {[member.mon, member.tue, member.wed, member.thu, member.fri].map((score, idx) => (
                    <div
                      key={idx}
                      className={cn(
                        "h-8 rounded flex items-center justify-center text-xs font-medium text-white",
                        getHeatColor(score)
                      )}
                    >
                      {score}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-center gap-4 mt-4 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-success" />
              <span className="text-muted-foreground">≥90</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-primary" />
              <span className="text-muted-foreground">80-89</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-warning" />
              <span className="text-muted-foreground">70-79</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-destructive" />
              <span className="text-muted-foreground">&lt;70</span>
            </div>
          </div>
        </div>

        {/* Top Performers */}
        <div className="bg-card rounded-2xl p-6 border border-border">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-foreground">本周之星</h2>
            <span className="text-xs text-muted-foreground">按绩效分排名</span>
          </div>

          <div className="space-y-4">
            {weeklyReport.topPerformers.map((performer, index) => (
              <div
                key={performer.name}
                className={cn(
                  "flex items-center gap-4 p-4 rounded-xl",
                  index === 0 && "bg-gold/10 border border-gold/30"
                )}
              >
                <div className={cn(
                  "w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold",
                  index === 0 && "rank-gold",
                  index === 1 && "rank-silver",
                  index === 2 && "rank-bronze"
                )}>
                  {index + 1}
                </div>
                <div className="flex-1">
                  <p className="font-medium text-foreground">{performer.name}</p>
                  <p className="text-sm text-muted-foreground">本周激励 ¥{performer.bonus.toLocaleString()}</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-foreground mono-number">{performer.score}</p>
                  <p className="text-xs text-muted-foreground">绩效分</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

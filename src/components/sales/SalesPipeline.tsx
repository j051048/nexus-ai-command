import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Target,
  Mail,
  Phone,
  Calendar,
  TrendingUp,
  Sparkles,
  ChevronRight,
  User,
  Building,
  Zap,
} from 'lucide-react';
import { SalesLead } from '@/types/nexus';

const mockLeads: SalesLead[] = [
  {
    id: '1',
    name: '张教授',
    company: '北京大学物理系',
    title: '实验室主任',
    score: 92,
    stage: 'negotiation',
    aiSuggestion: '建议今日下午跟进，讨论最终报价',
    lastContact: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2),
    winProbability: 78,
  },
  {
    id: '2',
    name: '李博士',
    company: '清华大学化学系',
    title: '研究员',
    score: 85,
    stage: 'proposal',
    aiSuggestion: '报价已发送5天，建议电话确认',
    lastContact: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5),
    winProbability: 65,
  },
  {
    id: '3',
    name: '王主任',
    company: '中科院物理所',
    title: '设备采购负责人',
    score: 78,
    stage: 'qualified',
    aiSuggestion: '需求明确，可安排产品演示',
    lastContact: new Date(Date.now() - 1000 * 60 * 60 * 24),
    winProbability: 55,
  },
  {
    id: '4',
    name: '陈教授',
    company: '浙江大学材料系',
    title: '课题组长',
    score: 72,
    stage: 'contacted',
    aiSuggestion: '初步接触，需深入了解需求',
    lastContact: new Date(Date.now() - 1000 * 60 * 60 * 3),
    winProbability: 40,
  },
  {
    id: '5',
    name: '刘工程师',
    company: '华为研究院',
    title: '测试部主管',
    score: 68,
    stage: 'new',
    aiSuggestion: 'AI推荐高质量线索，建议24h内联系',
    winProbability: 30,
  },
];

const stages = [
  { id: 'new', name: '新线索', color: 'bg-muted-foreground' },
  { id: 'contacted', name: '已联系', color: 'bg-primary' },
  { id: 'qualified', name: '已确认需求', color: 'bg-primary' },
  { id: 'proposal', name: '报价中', color: 'bg-warning' },
  { id: 'negotiation', name: '谈判中', color: 'bg-success' },
];

const todayLeads = [
  { id: '1', name: '张教授', company: '北大物理系', priority: 1, reason: 'AI预测今日是最佳跟进时间' },
  { id: '2', name: '李博士', company: '清华化学系', priority: 2, reason: '报价超时5天' },
  { id: '3', name: '刘工程师', company: '华为研究院', priority: 3, reason: '新线索，需24h内联系' },
];

export function SalesPipeline() {
  const [selectedLead, setSelectedLead] = useState<SalesLead | null>(null);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">销售AI管理</h1>
          <p className="text-muted-foreground mt-1">AI智能分析，精准跟进每一个商机</p>
        </div>
      </div>

      {/* Today's Priority Leads */}
      <div className="bg-gradient-card rounded-2xl p-6 cyber-border">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center pulse-live">
            <Target className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">今日AI推荐跟进</h2>
            <p className="text-xs text-muted-foreground">AI根据最佳时机自动排序</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {todayLeads.map((lead, index) => (
            <div
              key={lead.id}
              className={cn(
                "p-4 rounded-xl border transition-all cursor-pointer hover:scale-[1.02]",
                index === 0 ? "border-primary bg-primary/10" : "border-border bg-card"
              )}
            >
              <div className="flex items-start justify-between mb-3">
                <div className={cn(
                  "w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold",
                  index === 0 && "rank-gold",
                  index === 1 && "rank-silver",
                  index === 2 && "rank-bronze"
                )}>
                  {lead.priority}
                </div>
                {index === 0 && (
                  <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-primary text-primary-foreground flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    最佳时机
                  </span>
                )}
              </div>
              <h3 className="font-medium text-foreground">{lead.name}</h3>
              <p className="text-sm text-muted-foreground">{lead.company}</p>
              <p className="text-xs text-primary mt-2">{lead.reason}</p>
              <div className="flex gap-2 mt-4">
                <button className="flex-1 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors flex items-center justify-center gap-1">
                  <Phone className="w-3 h-3" />
                  立即联系
                </button>
                <button className="px-3 py-2 rounded-lg bg-secondary text-foreground text-xs font-medium hover:bg-secondary/80 transition-colors">
                  <Mail className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Pipeline Kanban */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">实时销售管道</h2>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
            AI实时赢率分析
          </div>
        </div>

        <div className="flex gap-4 overflow-x-auto pb-4">
          {stages.map((stage) => {
            const stageLeads = mockLeads.filter(l => l.stage === stage.id);
            return (
              <div key={stage.id} className="flex-shrink-0 w-72">
                <div className="flex items-center gap-2 mb-3">
                  <div className={cn("w-3 h-3 rounded-full", stage.color)} />
                  <span className="text-sm font-medium text-foreground">{stage.name}</span>
                  <span className="text-xs text-muted-foreground">({stageLeads.length})</span>
                </div>

                <div className="space-y-3">
                  {stageLeads.map((lead) => (
                    <div
                      key={lead.id}
                      onClick={() => setSelectedLead(lead)}
                      className="p-4 rounded-xl bg-secondary/50 border border-border hover:border-primary/50 transition-all cursor-pointer active-card"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                            <User className="w-4 h-4 text-primary" />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-foreground">{lead.name}</p>
                            <p className="text-xs text-muted-foreground">{lead.title}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold text-foreground mono-number">{lead.winProbability}%</p>
                          <p className="text-xs text-muted-foreground">赢率</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1 text-xs text-muted-foreground mb-3">
                        <Building className="w-3 h-3" />
                        {lead.company}
                      </div>

                      {/* AI Suggestion */}
                      <div className="p-2 rounded-lg bg-primary/10 border border-primary/20">
                        <div className="flex items-start gap-2">
                          <Sparkles className="w-3 h-3 text-primary mt-0.5" />
                          <p className="text-xs text-primary">{lead.aiSuggestion}</p>
                        </div>
                      </div>

                      {/* Score Impact */}
                      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border">
                        <span className="text-xs text-muted-foreground">绩效影响</span>
                        <span className="text-xs text-success font-medium flex items-center gap-1">
                          <Zap className="w-3 h-3" />
                          +{Math.floor(lead.winProbability / 10)} 分
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Lead Detail Modal */}
      {selectedLead && (
        <div
          className="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => setSelectedLead(null)}
        >
          <div
            className="bg-card rounded-2xl p-6 w-full max-w-lg border border-border shadow-2xl animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-xl bg-gradient-primary flex items-center justify-center">
                  <User className="w-7 h-7 text-primary-foreground" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground">{selectedLead.name}</h2>
                  <p className="text-muted-foreground">{selectedLead.company}</p>
                  <p className="text-sm text-muted-foreground">{selectedLead.title}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedLead(null)}
                className="text-muted-foreground hover:text-foreground"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="p-4 rounded-xl bg-secondary text-center">
                <p className="text-3xl font-bold text-foreground mono-number">{selectedLead.winProbability}%</p>
                <p className="text-xs text-muted-foreground">AI赢率预测</p>
              </div>
              <div className="p-4 rounded-xl bg-secondary text-center">
                <p className="text-3xl font-bold text-success mono-number">+{Math.floor(selectedLead.winProbability / 10)}</p>
                <p className="text-xs text-muted-foreground">绩效影响分</p>
              </div>
              <div className="p-4 rounded-xl bg-secondary text-center">
                <p className="text-3xl font-bold text-primary mono-number">{selectedLead.score}</p>
                <p className="text-xs text-muted-foreground">线索评分</p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-primary/10 border border-primary/30 mb-6">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium text-primary">AI建议行动</span>
              </div>
              <p className="text-sm text-foreground">{selectedLead.aiSuggestion}</p>
            </div>

            <div className="flex gap-3">
              <button className="flex-1 py-3 rounded-xl bg-gradient-primary text-primary-foreground font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-2">
                <Phone className="w-4 h-4" />
                立即联系
              </button>
              <button className="flex-1 py-3 rounded-xl bg-secondary text-foreground font-medium hover:bg-secondary/80 transition-colors flex items-center justify-center gap-2">
                <Mail className="w-4 h-4" />
                AI生成邮件
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

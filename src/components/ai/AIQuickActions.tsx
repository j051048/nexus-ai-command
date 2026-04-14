import React from 'react';
import { Sparkles, UserPlus, BarChart3, FileCheck, TrendingUp, AlertTriangle } from 'lucide-react';

interface QuickAction {
  label: string;
  prompt: string;
  icon: React.ReactNode;
}

const ACTIONS_BY_PAGE: Record<string, QuickAction[]> = {
  crm: [
    { label: 'AI 分析客户健康度', prompt: '帮我分析当前客户的整体健康度，找出需要重点关注的客户', icon: <BarChart3 size={14} /> },
    { label: 'AI 快速建客户', prompt: '帮我创建客户，', icon: <UserPlus size={14} /> },
    { label: 'AI 生成跟进建议', prompt: '根据最近的客户跟进情况，给我一些跟进建议', icon: <Sparkles size={14} /> },
  ],
  approval: [
    { label: 'AI 查询待审批', prompt: '列出所有需要我审批的申请，按紧急程度排序', icon: <FileCheck size={14} /> },
    { label: 'AI 解读审批趋势', prompt: '分析最近一个月的审批数据，有什么异常吗？', icon: <TrendingUp size={14} /> },
  ],
  dashboard: [
    { label: 'AI 解读数据异常', prompt: '帮我分析今日的业务数据，有没有异常指标需要关注？', icon: <AlertTriangle size={14} /> },
    { label: 'AI 生成销售报告', prompt: '帮我生成一份本月的销售数据分析报告', icon: <BarChart3 size={14} /> },
    { label: 'AI 预测业绩', prompt: '预测本月业绩目标达成情况，给出建议', icon: <TrendingUp size={14} /> },
  ],
};

function triggerAIChat(prompt: string) {
  window.dispatchEvent(
    new CustomEvent('proactive-chat', { detail: { message: prompt } })
  );
}

export function AIQuickActions({ pageType }: { pageType: keyof typeof ACTIONS_BY_PAGE }) {
  const actions = ACTIONS_BY_PAGE[pageType];
  if (!actions || actions.length === 0) return null;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {actions.map((action) => (
        <button
          key={action.label}
          onClick={() => triggerAIChat(action.prompt)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors border border-primary/20"
        >
          {action.icon}
          {action.label}
        </button>
      ))}
    </div>
  );
}

export default AIQuickActions;

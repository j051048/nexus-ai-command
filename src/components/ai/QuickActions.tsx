/**
 * AI-First 快捷操作面板
 * 提供常用办公操作的快速入口，支持一键触发 AI 对话
 */

import React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Calendar,
  DollarSign,
  Users,
  ClipboardCheck,
  FileText,
  Clock,
  TrendingUp,
  Bell,
  Briefcase,
  MessageSquare,
  Zap,
  ChevronRight,
} from 'lucide-react';

interface QuickAction {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  prompt: string;
  color: string;
  badge?: string;
}

interface QuickActionsProps {
  userRole: 'employee' | 'manager' | 'boss';
  onActionClick: (prompt: string) => void;
}

// 员工快捷操作
const employeeActions: QuickAction[] = [
  {
    id: 'leave',
    title: '请假申请',
    description: '快速提交请假',
    icon: <Calendar className="w-5 h-5" />,
    prompt: '我想请假',
    color: 'text-blue-500 bg-blue-500/10',
  },
  {
    id: 'expense',
    title: '费用报销',
    description: '提交报销申请',
    icon: <DollarSign className="w-5 h-5" />,
    prompt: '我要报销',
    color: 'text-green-500 bg-green-500/10',
  },
  {
    id: 'attendance',
    title: '考勤查询',
    description: '查看本月考勤',
    icon: <Clock className="w-5 h-5" />,
    prompt: '查看我这个月的考勤记录',
    color: 'text-orange-500 bg-orange-500/10',
  },
  {
    id: 'salary',
    title: '薪资查询',
    description: '查看工资明细',
    icon: <FileText className="w-5 h-5" />,
    prompt: '查看我这个月的工资明细',
    color: 'text-purple-500 bg-purple-500/10',
  },
  {
    id: 'meeting',
    title: '预约会议',
    description: '快速约会议室',
    icon: <Users className="w-5 h-5" />,
    prompt: '我想预约一个会议',
    color: 'text-cyan-500 bg-cyan-500/10',
  },
  {
    id: 'performance',
    title: '我的绩效',
    description: '查看绩效得分',
    icon: <TrendingUp className="w-5 h-5" />,
    prompt: '查看我的绩效情况',
    color: 'text-pink-500 bg-pink-500/10',
  },
];

// 管理者额外操作
const managerActions: QuickAction[] = [
  {
    id: 'team_attendance',
    title: '团队考勤',
    description: '查看团队出勤',
    icon: <Users className="w-5 h-5" />,
    prompt: '查看我团队这个月的考勤情况',
    color: 'text-indigo-500 bg-indigo-500/10',
  },
  {
    id: 'team_performance',
    title: '绩效排行',
    description: '团队绩效排名',
    icon: <TrendingUp className="w-5 h-5" />,
    prompt: '查看团队绩效排行榜',
    color: 'text-amber-500 bg-amber-500/10',
  },
  {
    id: 'budget',
    title: '预算查询',
    description: '部门预算情况',
    icon: <Briefcase className="w-5 h-5" />,
    prompt: '查看部门预算使用情况',
    color: 'text-emerald-500 bg-emerald-500/10',
  },
];

// 领导专属操作
const bossActions: QuickAction[] = [
  {
    id: 'daily_briefing',
    title: '今日简报',
    description: 'AI 智能汇报',
    icon: <Zap className="w-5 h-5" />,
    prompt: '今天有什么事需要我处理？',
    color: 'text-yellow-500 bg-yellow-500/10',
    badge: '推荐',
  },
  {
    id: 'batch_approve',
    title: '快速审批',
    description: '处理待审批事项',
    icon: <ClipboardCheck className="w-5 h-5" />,
    prompt: '有哪些待审批的事项？',
    color: 'text-red-500 bg-red-500/10',
    badge: '3',
  },
  {
    id: 'business_dashboard',
    title: '经营看板',
    description: '核心经营指标',
    icon: <TrendingUp className="w-5 h-5" />,
    prompt: '看看本月经营情况',
    color: 'text-blue-500 bg-blue-500/10',
  },
  {
    id: 'team_insight',
    title: '团队洞察',
    description: '员工状态分析',
    icon: <Users className="w-5 h-5" />,
    prompt: '分析一下团队现在的状态',
    color: 'text-violet-500 bg-violet-500/10',
  },
  {
    id: 'announcement',
    title: '发布公告',
    description: '全员通知',
    icon: <Bell className="w-5 h-5" />,
    prompt: '我想发一个公告',
    color: 'text-orange-500 bg-orange-500/10',
  },
];

export function QuickActions({ userRole, onActionClick }: QuickActionsProps) {
  // 根据角色获取可用操作
  const getActionsForRole = () => {
    switch (userRole) {
      case 'boss':
        return [...bossActions, ...managerActions.slice(0, 2), ...employeeActions.slice(0, 2)];
      case 'manager':
        return [...managerActions, ...employeeActions];
      default:
        return employeeActions;
    }
  };

  const actions = getActionsForRole();

  return (
    <Card className="border-none shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <Zap className="w-4 h-4 text-primary" />
          快捷操作
          <span className="text-xs text-muted-foreground font-normal">点击直接对话</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {actions.slice(0, 6).map((action) => (
            <button
              key={action.id}
              onClick={() => onActionClick(action.prompt)}
              className={cn(
                'flex flex-col items-start p-3 rounded-xl border border-border/50',
                'hover:border-primary/30 hover:bg-accent/50 transition-all duration-200',
                'text-left group'
              )}
            >
              <div className="flex items-center justify-between w-full mb-2">
                <div className={cn('p-2 rounded-lg', action.color)}>
                  {action.icon}
                </div>
                {action.badge && (
                  <Badge 
                    variant={action.badge === '推荐' ? 'default' : 'secondary'}
                    className="text-[10px] px-1.5 py-0"
                  >
                    {action.badge}
                  </Badge>
                )}
              </div>
              <span className="text-sm font-medium text-foreground">{action.title}</span>
              <span className="text-xs text-muted-foreground">{action.description}</span>
            </button>
          ))}
        </div>

        {actions.length > 6 && (
          <Button
            variant="ghost"
            className="w-full mt-3 text-muted-foreground hover:text-foreground"
            size="sm"
          >
            查看更多操作
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

// 迷你版快捷操作（用于聊天面板）
export function QuickActionsMini({ onActionClick }: { onActionClick: (prompt: string) => void }) {
  const miniActions = [
    { icon: <Calendar className="w-4 h-4" />, prompt: '请假', label: '请假' },
    { icon: <DollarSign className="w-4 h-4" />, prompt: '报销', label: '报销' },
    { icon: <Clock className="w-4 h-4" />, prompt: '考勤', label: '考勤' },
    { icon: <TrendingUp className="w-4 h-4" />, prompt: '绩效', label: '绩效' },
  ];

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {miniActions.map((action, index) => (
        <Button
          key={index}
          variant="outline"
          size="sm"
          className="h-7 text-xs gap-1"
          onClick={() => onActionClick(action.prompt)}
        >
          {action.icon}
          {action.label}
        </Button>
      ))}
    </div>
  );
}

export default QuickActions;
import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useUser } from '@/contexts/UserContext';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ChevronRight,
  Lightbulb,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Clock,
  Target,
  FileText,
  Users,
  DollarSign,
  Calendar,
  Zap,
  ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { motion, AnimatePresence } from 'framer-motion';

interface CopilotSuggestion {
  id: string;
  type: 'action' | 'insight' | 'reminder' | 'opportunity';
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  action?: {
    label: string;
    route?: string;
    aiPrompt?: string;
  };
  context?: string;
  timestamp: Date;
}

interface CopilotSidebarProps {
  className?: string;
  onSuggestionAction?: (suggestion: CopilotSuggestion) => void;
  isExpanded?: boolean;
}

const typeConfig = {
  action: {
    icon: Zap,
    color: 'text-amber-500',
    bgColor: 'bg-amber-500/10',
    label: '快捷操作',
  },
  insight: {
    icon: Lightbulb,
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
    label: '洞察',
  },
  reminder: {
    icon: Clock,
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/10',
    label: '提醒',
  },
  opportunity: {
    icon: TrendingUp,
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
    label: '机会',
  },
};

// Context-aware suggestion generator
function generateSuggestions(
  pathname: string,
  userRole: string,
  _userData?: unknown
): CopilotSuggestion[] {
  const now = new Date();
  const suggestions: CopilotSuggestion[] = [];

  // Global suggestions
  suggestions.push({
    id: 'quick-report',
    type: 'action',
    title: '生成今日工作报告',
    description: 'AI 可以帮您汇总今日的工作内容和进展',
    priority: 'medium',
    action: {
      label: '生成报告',
      aiPrompt: '帮我生成今天的工作日报',
    },
    timestamp: now,
  });

  // Page-specific suggestions
  if (pathname.includes('/sales')) {
    suggestions.unshift({
      id: 'sales-followup',
      type: 'opportunity',
      title: '3个高优先级客户待跟进',
      description: '张教授(清华)、李主任(北大)、王经理(中科院)已超过3天未联系',
      priority: 'high',
      action: {
        label: '查看详情',
        route: '/sales',
      },
      context: 'sales',
      timestamp: now,
    });
    suggestions.push({
      id: 'sales-script',
      type: 'insight',
      title: '话术优化建议',
      description: '基于最近成交案例，AI 发现强调"售后服务"可提升15%转化率',
      priority: 'medium',
      action: {
        label: '查看话术',
        aiPrompt: '给我看一下最新的销售话术建议',
      },
      timestamp: now,
    });
  }

  if (pathname.includes('/approval')) {
    suggestions.unshift({
      id: 'pending-approvals',
      type: 'reminder',
      title: '待处理审批',
      description: '您有审批请求等待处理，部分已超过24小时',
      priority: 'high',
      action: {
        label: '立即处理',
        route: '/approval',
      },
      timestamp: now,
    });
  }

  if (pathname.includes('/dashboard') || pathname === '/') {
    if (userRole === 'boss' || userRole === 'founder') {
      suggestions.unshift({
        id: 'weekly-summary',
        type: 'insight',
        title: '本周团队绩效概览',
        description: '销售额环比增长12%，但客户投诉上升了5%',
        priority: 'high',
        action: {
          label: '查看详情',
          aiPrompt: '给我看本周的团队绩效详细分析',
        },
        timestamp: now,
      });
    }
  }

  if (pathname.includes('/documents')) {
    suggestions.unshift({
      id: 'doc-analysis',
      type: 'action',
      title: '批量分析文档',
      description: '选择多个文档让 AI 进行对比分析或摘要提取',
      priority: 'medium',
      action: {
        label: '开始分析',
        aiPrompt: '帮我分析最近上传的文档',
      },
      timestamp: now,
    });
  }

  // Time-based suggestions
  const hour = now.getHours();
  if (hour >= 17 && hour < 19) {
    suggestions.push({
      id: 'eod-report',
      type: 'reminder',
      title: '下班前整理',
      description: '建议在下班前完成今日工作总结和明日计划',
      priority: 'low',
      action: {
        label: '开始整理',
        aiPrompt: '帮我整理今天的工作并规划明天的任务',
      },
      timestamp: now,
    });
  }

  // Sort by priority
  const priorityOrder = { high: 0, medium: 1, low: 2 };
  return suggestions.sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]).slice(0, 5);
}

function SuggestionCard({
  suggestion,
  onAction,
}: {
  suggestion: CopilotSuggestion;
  onAction: (s: CopilotSuggestion) => void;
}) {
  const config = typeConfig[suggestion.type];
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={cn(
        'p-3 rounded-lg border transition-all hover:shadow-md cursor-pointer group',
        suggestion.priority === 'high' && 'border-l-4 border-l-destructive',
        suggestion.priority === 'medium' && 'border-l-4 border-l-warning',
        suggestion.priority === 'low' && 'border-l-4 border-l-muted-foreground'
      )}
      onClick={() => onAction(suggestion)}
    >
      <div className="flex gap-3">
        <div
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
            config.bgColor
          )}
        >
          <Icon className={cn('w-4 h-4', config.color)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn('text-xs font-medium', config.color)}>
              {config.label}
            </span>
          </div>
          <h4 className="text-sm font-medium text-foreground mt-0.5 line-clamp-1">
            {suggestion.title}
          </h4>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
            {suggestion.description}
          </p>
          {suggestion.action && (
            <div className="flex items-center gap-1 mt-2 text-xs text-primary opacity-0 group-hover:opacity-100 transition-opacity">
              <span>{suggestion.action.label}</span>
              <ArrowRight className="w-3 h-3" />
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export function CopilotSidebar({
  className,
  onSuggestionAction,
  isExpanded = true,
}: CopilotSidebarProps) {
  const { user } = useUser();
  const location = useLocation();
  const navigate = useNavigate();
  const [suggestions, setSuggestions] = useState<CopilotSuggestion[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Generate context-aware suggestions
  useEffect(() => {
    setIsLoading(true);
    // Simulate AI processing
    const timer = setTimeout(() => {
      const newSuggestions = generateSuggestions(
        location.pathname,
        user.role,
        user
      );
      setSuggestions(newSuggestions);
      setIsLoading(false);
    }, 500);

    return () => clearTimeout(timer);
  }, [location.pathname, user]);

  const handleAction = (suggestion: CopilotSuggestion) => {
    if (onSuggestionAction) {
      onSuggestionAction(suggestion);
    }

    if (suggestion.action?.route) {
      navigate(suggestion.action.route);
    }
  };

  if (!isExpanded) {
    return null;
  }

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">AI 助手建议</h3>
            <p className="text-xs text-muted-foreground">
              基于当前上下文的智能推荐
            </p>
          </div>
        </div>
      </div>

      {/* Suggestions List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-24 rounded-lg bg-muted/50 animate-pulse"
              />
            ))}
          </div>
        ) : (
          <AnimatePresence mode="popLayout">
            {suggestions.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                onAction={handleAction}
              />
            ))}
          </AnimatePresence>
        )}

        {!isLoading && suggestions.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            <CheckCircle2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">暂无建议</p>
            <p className="text-xs mt-1">一切看起来都很好！</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t bg-muted/30">
        <Button
          variant="ghost"
          size="sm"
          className="w-full text-xs justify-start gap-2"
          onClick={() => onSuggestionAction?.({
            id: 'ask-ai',
            type: 'action',
            title: '询问 AI',
            description: '',
            priority: 'low',
            action: { aiPrompt: '' },
            timestamp: new Date(),
          })}
        >
          <Sparkles className="w-3 h-3" />
          有其他问题？直接问 AI
          <ChevronRight className="w-3 h-3 ml-auto" />
        </Button>
      </div>
    </div>
  );
}

export default CopilotSidebar;

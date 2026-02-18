import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useUser } from '@/contexts/UserContext';
import {
  Target,
  Gift,
  AlertTriangle,
  TrendingUp,
  MessageSquare,
  Trophy,
  Zap,
  Clock,
} from 'lucide-react';
import { ActiveCard } from '@/types/nexus';
import { useApprovals } from '@/hooks/useApprovals';
import { useToast } from '@/hooks/use-toast';

const cardIcons = {
  lead: <Target className="w-4 h-4" />,
  bonus: <Gift className="w-4 h-4" />,
  alert: <AlertTriangle className="w-4 h-4" />,
  ranking: <Trophy className="w-4 h-4" />,
  task: <Clock className="w-4 h-4" />,
  script: <MessageSquare className="w-4 h-4" />,
};

const priorityStyles = {
  urgent: 'border-l-4 border-l-destructive bg-destructive/5',
  high: 'border-l-4 border-l-warning bg-warning/5',
  medium: 'border-l-4 border-l-primary bg-primary/5',
  low: 'border-l-4 border-l-muted-foreground',
};

import { useNavigate } from 'react-router-dom';

export function ActiveCardStream() {
  const { user } = useUser();
  const [cards, setCards] = useState<ActiveCard[]>([]);
  const [newCardId, setNewCardId] = useState<string | null>(null);
  const navigate = useNavigate();

  // Real Data Hook
  const { pendingApprovals, updateStatus, isLoading: isLoadingApprovals } = useApprovals();
  const { toast } = useToast();

  useEffect(() => {
    // Convert Real Approvals to Cards
    const approvalCards: ActiveCard[] = pendingApprovals.map(req => ({
      id: req.id,
      type: 'alert',
      title: '⚠️ 待审批申请',
      content: `${req.submitter_name} 提交了 ${req.description || '费用'} 申请 (¥${req.amount})，请审批`,
      priority: 'urgent',
      timestamp: new Date(req.created_at),
    }));

    // Sort by time
    const allCards = [...approvalCards].sort((a, b) =>
      b.timestamp.getTime() - a.timestamp.getTime()
    );

    setCards(allCards);
  }, [user.role, pendingApprovals]);

  const handleApprove = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await updateStatus.mutateAsync({ id, status: 'approved' });
      toast({ title: "已批准", description: "申请已通过系统审核" });
    } catch (e) {
      toast({ variant: "destructive", title: "操作失败", description: "无法完成请求" });
    }
  };

  const handleReject = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await updateStatus.mutateAsync({ id, status: 'rejected' });
      toast({ title: "已驳回", description: "申请已被拒绝" });
    } catch (e) {
      toast({ variant: "destructive", title: "操作失败", description: "无法完成请求" });
    }
  };

  const handleCardClick = (card: ActiveCard) => {
    switch (card.type) {
      case 'alert':
        navigate('/approval');
        break;
      case 'bonus':
        navigate('/rewards');
        break;
      case 'lead':
        navigate('/sales');
        break;
      case 'ranking':
        navigate(user.role === 'boss' ? '/boss-dashboard' : '/dashboard');
        break;
      case 'task':
        navigate('/sales'); // Tasks usually related to sales
        break;
      default:
        break;
    }
  };

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000 / 60);
    if (diff < 1) return '刚刚';
    if (diff < 60) return `${diff}分钟前`;
    return `${Math.floor(diff / 60)}小时前`;
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {cards.length === 0 && (
        <div className="text-center py-8 text-sm text-muted-foreground">暂无消息</div>
      )}
      {cards.map((card) => (
        <div
          key={card.id}
          onClick={() => handleCardClick(card)}
          className={cn(
            "rounded-lg p-4 active-card transition-all duration-300 cursor-pointer hover:shadow-md",
            priorityStyles[card.priority],
            newCardId === card.id && "slide-in-right"
          )}
        >
          <div className="flex items-start gap-3">
            <div className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
              card.type === 'bonus' && "bg-success/20 text-success",
              card.type === 'lead' && "bg-primary/20 text-primary",
              card.type === 'alert' && "bg-destructive/20 text-destructive",
              card.type === 'ranking' && "bg-gold/20 text-gold",
              card.type === 'task' && "bg-warning/20 text-warning",
              card.type === 'script' && "bg-primary/20 text-primary",
            )}>
              {cardIcons[card.type]}
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-medium text-foreground">{card.title}</h4>
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{card.content}</p>
              <p className="text-xs text-muted-foreground/60 mt-2">{formatTime(card.timestamp)}</p>
            </div>
          </div>
          {card.type === 'bonus' && (
            <div className="mt-3 flex justify-end">
              <button className="text-xs font-medium text-success hover:text-success/80 transition-colors">
                查看奖金明细 →
              </button>
            </div>
          )}
          {card.type === 'alert' && (
            <div className="mt-3 flex gap-2 justify-end">
              <button
                onClick={(e) => handleReject(card.id, e)}
                className="px-3 py-1.5 text-xs font-medium rounded-md bg-destructive/20 text-destructive hover:bg-destructive/30 transition-colors"
              >
                驳回
              </button>
              <button
                onClick={(e) => handleApprove(card.id, e)}
                className="px-3 py-1.5 text-xs font-medium rounded-md bg-success text-success-foreground hover:bg-success/90 transition-colors"
              >
                批准
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

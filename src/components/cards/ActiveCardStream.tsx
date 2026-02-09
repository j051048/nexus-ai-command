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

const mockEmployeeCards: ActiveCard[] = [
  {
    id: '1',
    type: 'bonus',
    title: '🎉 即时奖金到账！',
    content: '恭喜！成功推进"北大物理系"商机至技术验证阶段，触发 ¥300 即时奖金！',
    priority: 'high',
    timestamp: new Date(),
  },
  {
    id: '2',
    type: 'lead',
    title: '📍 高优线索推荐',
    content: '张教授（清华化学系）对光谱仪表现出强烈兴趣，建议今日跟进',
    priority: 'high',
    timestamp: new Date(Date.now() - 1000 * 60 * 5),
  },
  {
    id: '3',
    type: 'script',
    title: '💡 话术建议',
    content: '检测到客户提到"预算有限"，建议回复：我们可以提供灵活的分期方案...',
    priority: 'medium',
    timestamp: new Date(Date.now() - 1000 * 60 * 15),
  },
  {
    id: '4',
    type: 'ranking',
    title: '🏆 排行榜更新',
    content: '您已升至本周销售榜第3名！距离第2名还差 150 分',
    priority: 'medium',
    timestamp: new Date(Date.now() - 1000 * 60 * 30),
  },
  {
    id: '5',
    type: 'task',
    title: '⏰ 跟进提醒',
    content: '李教授的报价已发送3天，建议今日电话确认',
    priority: 'low',
    timestamp: new Date(Date.now() - 1000 * 60 * 60),
  },
];

const mockBossCards: ActiveCard[] = [
  {
    id: '1',
    type: 'alert',
    title: '⚠️ 超预算审批',
    content: '采购单#2024-089 超出预算限额10%，需您确认',
    priority: 'urgent',
    timestamp: new Date(),
  },
  {
    id: '2',
    type: 'ranking',
    title: '📊 团队周报生成',
    content: 'AI已生成本周销售团队绩效报告，点击查看详情',
    priority: 'high',
    timestamp: new Date(Date.now() - 1000 * 60 * 30),
  },
  {
    id: '3',
    type: 'bonus',
    title: '💰 激励发放通知',
    content: '本周自动发放即时奖金 ¥8,500，共触发12次激励事件',
    priority: 'medium',
    timestamp: new Date(Date.now() - 1000 * 60 * 60),
  },
];

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
    // Base Mocks (Keep these to make the UI look alive for non-approval items)
    const baseMocks = user.role === 'boss'
      ? mockBossCards.filter(c => c.type !== 'alert') // Remove mock alerts, use real ones
      : mockEmployeeCards;

    // Convert Real Approvals to Cards
    const approvalCards: ActiveCard[] = pendingApprovals.map(req => ({
      id: req.id,
      type: 'alert',
      title: '⚠️ 待审批申请',
      content: `${req.submitter_name} 提交了 ${req.description || '费用'} 申请 (¥${req.amount})，请审批`,
      priority: 'urgent',
      timestamp: new Date(req.created_at),
    }));

    // Combine and Sort
    const allCards = [...approvalCards, ...baseMocks].sort((a, b) =>
      b.timestamp.getTime() - a.timestamp.getTime()
    );

    setCards(allCards);
  }, [user.role, pendingApprovals]);

  // Simulate new card arriving (Only for employees for now, or non-critical updates)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (user.role === 'employee') {
        const newCard: ActiveCard = {
          id: 'new-' + Date.now(),
          type: 'bonus',
          title: '🎉 即时奖金到账！',
          content: '通话质量评分达到90+，触发 ¥200 即时奖金！',
          priority: 'high',
          timestamp: new Date(),
        };
        setCards(prev => [newCard, ...prev]);
        setNewCardId(newCard.id);
        setTimeout(() => setNewCardId(null), 1000);
      }
    }, 5000);

    return () => clearTimeout(timer);
  }, [user.role]);

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

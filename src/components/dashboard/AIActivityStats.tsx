import { useEffect, useState } from 'react';
import { Bot, Clock, CheckCircle2, TrendingUp } from 'lucide-react';
import { aiClient } from '@/api/aiClient';

interface AIStats {
  tasks_completed: number;
  estimated_hours_saved: number;
  active_agents: number;
}

export function AIActivityStats() {
  const [stats, setStats] = useState<AIStats | null>(null);

  useEffect(() => {
    aiClient.get('/api/dashboard/ai-stats')
      .then((res) => {
        const payload = (res as { data?: { data?: AIStats } | AIStats })?.data;
        const actualData = (payload && 'data' in payload) ? payload.data : payload;
        if (actualData) setStats(actualData as AIStats);
      })
      .catch(() => {});
  }, []);

  if (!stats) return null;

  const items = [
    {
      icon: CheckCircle2,
      label: '本周 AI 完成任务',
      value: `${stats.tasks_completed} 项`,
      color: 'text-green-500',
      bg: 'bg-green-500/10',
    },
    {
      icon: Clock,
      label: '预计节省时间',
      value: `${stats.estimated_hours_saved} 小时`,
      color: 'text-blue-500',
      bg: 'bg-blue-500/10',
    },
    {
      icon: Bot,
      label: '活跃 Agent 数',
      value: `${stats.active_agents} 个`,
      color: 'text-purple-500',
      bg: 'bg-purple-500/10',
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div
            key={item.label}
            className="flex items-center gap-3 p-4 rounded-xl bg-card border border-border/50 hover:border-border transition-colors"
          >
            <div className={`p-2 rounded-lg ${item.bg}`}>
              <Icon className={`w-5 h-5 ${item.color}`} />
            </div>
            <div>
              <p className="text-lg font-bold">{item.value}</p>
              <p className="text-xs text-muted-foreground">{item.label}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

import { useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, FileCheck, Mic, UserRoundSearch } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { usePendingApprovalsCount } from '@/hooks/useApprovals';
import { cn } from '@/lib/utils';

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

export function MobileActionCardStack() {
  const navigate = useNavigate();
  const touchStartX = useRef(0);
  const pendingApprovals = usePendingApprovalsCount().data ?? 0;

  const cards = [
    {
      id: 'approval',
      title: '审批速办',
      description: pendingApprovals > 0 ? `${pendingApprovals} 条审批等待处理` : '暂无审批积压',
      icon: FileCheck,
      tone: 'bg-blue-500/10 text-blue-600',
      primary: '去处理',
      onPrimary: () => navigate('/approval'),
      swipePrompt: '请把待审批事项按风险和截止时间排个序。',
    },
    {
      id: 'customer',
      title: '客户跟进',
      description: '快速记录拜访、补齐下一步动作',
      icon: UserRoundSearch,
      tone: 'bg-amber-500/10 text-amber-600',
      primary: '打开 CRM',
      onPrimary: () => navigate('/crm'),
      swipePrompt: '请生成今天最应该跟进的客户清单，并给出每个客户的下一步动作。',
    },
    {
      id: 'voice',
      title: '语音拜访速记',
      description: '长按 AI 按钮或点这里开始口述',
      icon: Mic,
      tone: 'bg-emerald-500/10 text-emerald-600',
      primary: '开始速记',
      onPrimary: () =>
        triggerAI('启动语音拜访速记：请提示我口述客户名称、参会人、需求、异议、预算、下一步动作和跟进日期。'),
      swipePrompt: '请把我接下来的口述整理成客户拜访记录草稿。',
    },
  ];

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-sm font-semibold">移动高频动作</h2>
        <span className="text-[11px] text-muted-foreground">右滑采纳 / 左滑稍后</span>
      </div>
      <div className="grid gap-2">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <article
              key={card.id}
              className="rounded-lg border bg-card p-3 shadow-sm"
              onTouchStart={(event) => {
                touchStartX.current = event.touches[0]?.clientX ?? 0;
              }}
              onTouchEnd={(event) => {
                const endX = event.changedTouches[0]?.clientX ?? touchStartX.current;
                const delta = endX - touchStartX.current;
                if (Math.abs(delta) < 48) return;
                if (delta > 0) {
                  toast.success(`${card.title}已加入今日计划`);
                  triggerAI(card.swipePrompt);
                } else {
                  toast.info(`${card.title}已稍后提醒`);
                }
              }}
            >
              <div className="flex items-center gap-3">
                <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-lg', card.tone)}>
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{card.title}</div>
                  <div className="truncate text-xs text-muted-foreground">{card.description}</div>
                </div>
                <Button size="sm" variant="outline" onClick={card.onPrimary}>
                  {card.primary}
                </Button>
              </div>
            </article>
          );
        })}
      </div>
      <div className="flex items-center gap-2 rounded-lg bg-muted/40 px-3 py-2 text-[11px] text-muted-foreground">
        <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
        拜访后优先用语音速记，AI 会自动抽取客户、需求、异议、预算和下一步动作。
      </div>
    </section>
  );
}

export default MobileActionCardStack;

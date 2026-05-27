import { useState } from 'react';
import { AlertCircle, CheckCircle2, ThumbsDown, ThumbsUp } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { httpClient } from '@/lib/httpClient';
import { cn } from '@/lib/utils';

type FeedbackSignal = 'useful' | 'incorrect' | 'blocked';

interface ExperienceFeedbackProps {
  surface: string;
  targetId?: string;
  className?: string;
}

const FEEDBACK_ACTIONS: Array<{
  signal: FeedbackSignal;
  label: string;
  icon: typeof ThumbsUp;
}> = [
  { signal: 'useful', label: '有帮助', icon: ThumbsUp },
  { signal: 'incorrect', label: '不准确', icon: ThumbsDown },
  { signal: 'blocked', label: '没解决', icon: AlertCircle },
];

function saveLocalFeedback(payload: Record<string, unknown>) {
  const key = 'nexus.experienceFeedback';
  const existing = JSON.parse(window.localStorage.getItem(key) || '[]') as unknown[];
  window.localStorage.setItem(key, JSON.stringify([payload, ...existing].slice(0, 50)));
}

export function ExperienceFeedback({ surface, targetId, className }: ExperienceFeedbackProps) {
  const [selected, setSelected] = useState<FeedbackSignal | null>(null);

  const submit = async (signal: FeedbackSignal) => {
    const payload = {
      surface,
      target_id: targetId,
      signal,
      path: window.location.pathname,
      created_at: new Date().toISOString(),
    };
    setSelected(signal);
    try {
      await httpClient.post('/api/feedback/experience', payload);
    } catch {
      saveLocalFeedback(payload);
    }
    toast.success('反馈已记录，会进入体验质量复盘');
  };

  return (
    <div className={cn('flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground', className)}>
      <div className="inline-flex items-center gap-1.5">
        <CheckCircle2 className="h-3.5 w-3.5" />
        这条 AI 建议是否有用？
      </div>
      <div className="flex flex-wrap gap-1.5">
        {FEEDBACK_ACTIONS.map(({ signal, label, icon: Icon }) => (
          <Button
            key={signal}
            type="button"
            size="sm"
            variant={selected === signal ? 'default' : 'ghost'}
            className="h-7 px-2 text-xs"
            onClick={() => submit(signal)}
          >
            <Icon className="mr-1 h-3.5 w-3.5" />
            {label}
          </Button>
        ))}
      </div>
    </div>
  );
}

export default ExperienceFeedback;

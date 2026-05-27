import { useState, type ElementType, type ReactNode } from 'react';
import { AlertTriangle, ArrowRight, Bot } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ExperienceFeedback } from '@/components/feedback/ExperienceFeedback';
import { httpClient } from '@/lib/httpClient';
import { cn } from '@/lib/utils';
import { AITrustBadge, type AITrustLevel } from './AITrustBadge';

export interface AIInsightEvidence {
  label: string;
  value: ReactNode;
}

export interface AIInsightAction {
  actionId?: string;
  label: string;
  prompt?: string;
  href?: string;
  variant?: 'default' | 'outline' | 'ghost' | 'destructive';
  riskLevel?: 'low' | 'medium' | 'high';
  requiresConfirmation?: boolean;
  executeEndpoint?: string;
  method?: 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  payload?: unknown;
  evidence?: AIInsightEvidence[];
  onClick?: () => void;
}

interface AIInsightPanelProps {
  title: string;
  summary: ReactNode;
  trustLevel?: AITrustLevel;
  score?: number;
  icon?: ElementType;
  evidence?: AIInsightEvidence[];
  risks?: string[];
  context?: string[];
  actions?: AIInsightAction[];
  className?: string;
}

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

export function AIInsightPanel({
  title,
  summary,
  trustLevel = 'medium',
  score,
  icon: Icon = Bot,
  evidence = [],
  risks = [],
  context = [],
  actions = [],
  className,
}: AIInsightPanelProps) {
  const navigate = useNavigate();
  const [executingAction, setExecutingAction] = useState<string | null>(null);

  const handleAction = async (action: AIInsightAction) => {
    if (action.onClick) {
      action.onClick();
      return;
    }
    if (action.requiresConfirmation) {
      const confirmed = window.confirm(`确认执行「${action.label}」？高风险或外发动作会保留审计记录。`);
      if (!confirmed) return;
    }
    if (action.executeEndpoint) {
      const actionKey = action.actionId || action.label;
      setExecutingAction(actionKey);
      try {
        await httpClient.request({
          url: action.executeEndpoint,
          method: action.method || 'POST',
          data: action.payload ?? {},
        });
        toast.success(`${action.label} 已提交`);
      } catch (error) {
        const message = error instanceof Error ? error.message : '动作执行失败';
        toast.error(message);
      } finally {
        setExecutingAction(null);
      }
      return;
    }
    if (action.href) {
      navigate(action.href);
      return;
    }
    if (action.prompt) triggerAI(action.prompt);
  };

  return (
    <section data-testid="ai-insight-panel" className={cn('rounded-lg border bg-card p-4 shadow-sm', className)}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold">{title}</h2>
              <AITrustBadge level={trustLevel} score={score} />
            </div>
            <div className="mt-1 text-sm leading-6 text-muted-foreground">{summary}</div>
            {context.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {context.map((item) => (
                  <Badge key={item} variant="outline" className="bg-background/70 text-[11px]">
                    {item}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>

        {actions.length > 0 && (
          <div className="flex flex-wrap gap-2 lg:justify-end">
            {actions.map((action) => {
              const actionKey = action.actionId || action.label;
              return (
                <Button
                  key={actionKey}
                  size="sm"
                  variant={action.variant ?? 'outline'}
                  disabled={executingAction === actionKey}
                  onClick={() => handleAction(action)}
                >
                  {executingAction === actionKey ? '执行中...' : action.label}
                  {(action.href || action.prompt || action.executeEndpoint) && <ArrowRight className="ml-1.5 h-3.5 w-3.5" />}
                </Button>
              );
            })}
          </div>
        )}
      </div>

      {(evidence.length > 0 || risks.length > 0) && (
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {evidence.map((item) => (
            <div key={item.label} className="rounded-lg border bg-muted/30 p-3">
              <div className="text-xs text-muted-foreground">{item.label}</div>
              <div className="mt-1 text-sm font-medium text-foreground">{item.value}</div>
            </div>
          ))}
          {risks.length > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
              <div className="flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-300">
                <AlertTriangle className="h-3.5 w-3.5" />
                需人工关注
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {risks.map((risk) => (
                  <Badge key={risk} variant="outline" className="border-amber-500/30 bg-background/60 text-[11px]">
                    {risk}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <ExperienceFeedback
        surface="ai_insight_panel"
        targetId={title}
        className="mt-4 border-t pt-3"
      />
    </section>
  );
}

export default AIInsightPanel;

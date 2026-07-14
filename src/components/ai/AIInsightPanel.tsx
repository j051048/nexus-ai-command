import { useState, type ElementType, type ReactNode } from 'react';
import { AlertTriangle, ArrowRight, Bot, MoreHorizontal } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
  /** 显式禁用按钮（如缺少前置文件、诊断进行中）。 */
  disabled?: boolean;
}

/**
 * 紧凑统计项：用于嵌入型洞察条右侧的数字摘要（待处理/到期/最高额…）。
 * 仅在 variant="compact" 下渲染，避免占用 default 版的纵向空间。
 */
export interface AIInsightStat {
  label: string;
  value: ReactNode;
}

interface AIInsightPanelProps {
  surfaceId: string;
  title: string;
  summary: ReactNode;
  trustLevel?: AITrustLevel;
  score?: number;
  icon?: ElementType;
  evidence?: AIInsightEvidence[];
  risks?: string[];
  context?: string[];
  actions?: AIInsightAction[];
  /**
   * 布局密度。
   * - default：页首主洞察，p-4 + 三列证据网格 + 多按钮，适合收件箱顶部。
   * - compact：页内嵌入窄横幅，px-3 py-2.5 + 单行统计 + 1-2 按钮，适合
   *   审批/合同/CRM/标书等业务页面顶部，不占用过多纵向空间。
   */
  variant?: 'default' | 'compact';
  /** compact 专属：右侧摘要统计（待处理 N / 到期 N …）。default 下忽略。 */
  stats?: AIInsightStat[];
  className?: string;
}

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

export function AIInsightPanel({
  surfaceId,
  title,
  summary,
  trustLevel = 'medium',
  score,
  icon: Icon = Bot,
  evidence = [],
  risks = [],
  context = [],
  actions = [],
  variant = 'default',
  stats = [],
  className,
}: AIInsightPanelProps) {
  const isCompact = variant === 'compact';
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

  // ── compact 变体：页内嵌入窄横幅（审批/合同/CRM/标书等页面顶部）──
  if (isCompact) {
    const [primaryAction, ...secondaryActions] = actions;
    return (
      <section
        data-testid={`ai-insight-panel-${surfaceId}`}
        data-ai-surface={surfaceId}
        className={cn(
          'rounded-lg border border-l-2 border-l-primary/55 bg-card px-3 py-2.5',
          className,
        )}
      >
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border bg-muted/30 text-primary">
              <Icon className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-medium text-primary">建议</span>
                <h2 className="truncate text-sm font-medium">{title}</h2>
                <AITrustBadge level={trustLevel} score={score} />
              </div>
              {summary && (
                <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{summary}</p>
              )}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-3">
            {stats.length > 0 && (
              <div className="hidden gap-3 text-xs text-muted-foreground sm:flex">
                {stats.map((s) => (
                  <span key={s.label}>{s.label} {s.value}</span>
                ))}
              </div>
            )}
            {primaryAction && (() => {
              const action = primaryAction;
              const actionKey = action.actionId || action.label;
              return (
                <Button
                  key={actionKey}
                  size="sm"
                  variant={action.variant ?? 'outline'}
                  className="h-8"
                  disabled={action.disabled || executingAction === actionKey}
                  onClick={() => handleAction(action)}
                >
                  {executingAction === actionKey ? '执行中...' : action.label}
                </Button>
              );
            })()}
            {secondaryActions.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="icon" variant="ghost" className="h-8 w-8" aria-label="更多建议操作">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {secondaryActions.map((action) => {
                    const actionKey = action.actionId || action.label;
                    return (
                      <DropdownMenuItem
                        key={actionKey}
                        disabled={action.disabled || executingAction === actionKey}
                        onClick={() => handleAction(action)}
                      >
                        {executingAction === actionKey ? '执行中...' : action.label}
                      </DropdownMenuItem>
                    );
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>
      </section>
    );
  }

  // ── default 变体：页首主洞察（收件箱顶部等，p-4 + 证据网格）──
  return (
    <section
      data-testid={`ai-insight-panel-${surfaceId}`}
      data-ai-surface={surfaceId}
      className={cn(
        'rounded-lg border border-l-2 border-l-primary/55 bg-card p-4',
        className,
      )}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border bg-muted/30 text-primary">
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium text-primary">建议</span>
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
                  disabled={action.disabled || executingAction === actionKey}
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
        <div className="mt-4 grid divide-y border-y md:grid-cols-3 md:divide-x md:divide-y-0">
          {evidence.map((item) => (
            <div key={item.label} className="px-3 py-2.5 first:pl-0 last:pr-0">
              <div className="text-xs text-muted-foreground">{item.label}</div>
              <div className="mt-1 text-sm font-medium text-foreground">{item.value}</div>
            </div>
          ))}
          {risks.length > 0 && (
            <div className="px-3 py-2.5 first:pl-0 last:pr-0">
              <div className="flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-300">
                <AlertTriangle className="h-3.5 w-3.5" />
                需要你确认
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

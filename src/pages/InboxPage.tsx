/**
 * Unified action inbox.
 *
 * This is the action-first home surface shared by desktop, mobile, and AI
 * copilot. It consumes `/api/inbox/actions` so approvals, customer risks,
 * notifications, and Agent Ops actions use one interaction model.
 */

import { useMemo, useRef, useState, type ElementType } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  ExternalLink,
  FileCheck,
  Filter,
  Sparkles,
  UserRoundSearch,
} from 'lucide-react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AIOperatingSystemStrip } from '@/components/product/AIOperatingSystemStrip';
import { AIInsightPanel } from '@/components/ai/AIInsightPanel';
import { AITrustBadge, type AITrustLevel } from '@/components/ai/AITrustBadge';
import { WorkEmptyState, WorkErrorState, WorkLoadingState } from '@/components/common/WorkState';
import { useAuth } from '@/components/auth/AuthContext';
import { cn } from '@/lib/utils';
import {
  type ActionEventType,
  type ActionSource,
  type InboxActionCommand,
  type InboxActionItem,
  useExecuteInboxAction,
  useInboxActions,
  useRecordInboxActionEvent,
} from '@/hooks/useInboxActions';

type TabKey = 'all' | ActionSource;
type EvidenceItem = { label: string; value: string };

const SOURCE_META: Record<ActionSource, { label: string; icon: ElementType; tone: string }> = {
  approval: {
    label: '审批',
    icon: FileCheck,
    tone: 'text-blue-600 bg-blue-500/10',
  },
  notification: {
    label: '通知',
    icon: Bell,
    tone: 'text-sky-600 bg-sky-500/10',
  },
  crm: {
    label: '客户',
    icon: UserRoundSearch,
    tone: 'text-amber-600 bg-amber-500/10',
  },
  system: {
    label: '系统',
    icon: AlertTriangle,
    tone: 'text-muted-foreground bg-muted',
  },
};

const PRIORITY_LABEL = {
  urgent: '紧急',
  high: '高',
  medium: '中',
  low: '低',
};

const PRIORITY_CLASS = {
  urgent: 'border-destructive/40 bg-destructive/10 text-destructive',
  high: 'border-orange-500/40 bg-orange-500/10 text-orange-600',
  medium: 'border-primary/30 bg-primary/10 text-primary',
  low: 'border-muted bg-muted text-muted-foreground',
};

function formatTime(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getEvidence(item: InboxActionItem): EvidenceItem[] {
  const raw = item.metadata?.evidence;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((entry) => {
      if (!entry || typeof entry !== 'object') return null;
      const record = entry as Record<string, unknown>;
      const label = String(record.label ?? '').trim();
      const value = String(record.value ?? '').trim();
      return label && value ? { label, value } : null;
    })
    .filter(Boolean) as EvidenceItem[];
}

function getRiskFlags(item: InboxActionItem): string[] {
  const raw = item.metadata?.risk_flags;
  if (!Array.isArray(raw)) return [];
  return raw.map((value) => String(value)).filter(Boolean);
}

function getTrustLevel(item: InboxActionItem): AITrustLevel {
  const riskScore = Number(item.metadata?.risk_score ?? 0);
  if (item.priority === 'urgent' || riskScore >= 80) return 'low';
  if (item.priority === 'high' || riskScore >= 55) return 'medium';
  return 'high';
}

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

function ActionInboxInsightStrip({ items }: { items: InboxActionItem[] }) {
  const urgent = items.filter((item) => item.priority === 'urgent');
  const crmRisk = items.filter((item) => item.source === 'crm');
  const nextItem = urgent[0] || items.find((item) => item.priority === 'high') || items[0];

  if (!nextItem) return null;

  return (
    <section data-testid="ai-insight-panel" className="rounded-lg border bg-card px-3 py-2.5 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">今日行动台 · 建议先处理：{nextItem.title}</div>
            <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span>{items.length} 个待处理</span>
              <span>{urgent.length} 个紧急</span>
              <span>{crmRisk.length} 个客户风险</span>
              <span>基于 AI 证据链排序</span>
              <span>AI 优先级解释</span>
            </div>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-8"
            onClick={() => triggerAI('请用 3 条以内解释当前行动台为什么这样排序。')}
          >
            为什么这样排
          </Button>
          <Button
            size="sm"
            className="h-8"
            onClick={() => triggerAI('请把当前行动台整理成一份今天可以照着执行的工作计划。')}
          >
            生成计划
          </Button>
        </div>
      </div>
    </section>
  );
}

function RoleGuidanceStrip({ role }: { role?: string | null }) {
  const isBoss = role === 'boss' || role === 'founder';
  const isManager = role === 'manager';
  const title = isBoss ? '管理者今日视角' : isManager ? '团队负责人今日视角' : '个人执行视角';
  const items = isBoss
    ? ['先看高风险审批和合同', '复盘客户跟进断点', '让 AI 生成经营摘要']
    : isManager
      ? ['处理团队待审批', '推进高价值客户', '检查项目和合同节点']
      : ['清空个人待办', '记录客户拜访', '补齐审批材料'];

  return (
    <section className="rounded-lg border bg-muted/20 px-3 py-2">
      <div className="flex flex-col gap-2 text-sm md:flex-row md:items-center md:justify-between">
        <div className="font-medium">{title}</div>
        <div className="flex min-w-0 flex-wrap gap-2 text-xs text-muted-foreground">
          {items.map((item) => (
            <span key={item} className="rounded-full bg-background px-2 py-1">
              {item}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function InboxPage() {
  const navigate = useNavigate();
  const { role } = useAuth();
  const [activeTab, setActiveTab] = useState<TabKey>('all');
  const [expandedItemId, setExpandedItemId] = useState<string | null>(null);
  const [showLaterItems, setShowLaterItems] = useState(false);
  const touchStartX = useRef(0);
  const { data, isLoading, isError, refetch } = useInboxActions(50);
  const executeAction = useExecuteInboxAction();
  const recordActionEvent = useRecordInboxActionEvent();

  const items = data?.items ?? [];
  const visibleItems = useMemo(
    () => (activeTab === 'all' ? items : items.filter((item) => item.source === activeTab)),
    [activeTab, items],
  );

  const sourceCounts = useMemo(() => {
    const counts: Record<TabKey, number> = {
      all: items.length,
      approval: 0,
      notification: 0,
      crm: 0,
      system: 0,
    };
    items.forEach((item) => {
      counts[item.source] += 1;
    });
    return counts;
  }, [items]);

  const tabs: Array<{ key: TabKey; label: string; icon: ElementType }> = [
    { key: 'all', label: '全部行动', icon: Filter },
    { key: 'approval', label: '审批', icon: FileCheck },
    { key: 'crm', label: '客户风险', icon: UserRoundSearch },
    { key: 'notification', label: '通知', icon: Bell },
    { key: 'system', label: 'Agent Ops', icon: AlertTriangle },
  ];

  const handleCommand = async (item: InboxActionItem, command: InboxActionCommand) => {
    if (command.kind === 'navigate') {
      recordActionEvent.mutate({
        action: item,
        event_type: 'viewed',
        metadata: { command_id: command.id },
      });
      navigate(command.navigate_to || item.action_url || '/inbox');
      return;
    }
    try {
      await executeAction.mutateAsync(command);
      recordActionEvent.mutate({
        action: item,
        event_type: 'command_executed',
        metadata: { command_id: command.id, command_label: command.label },
      });
      toast.success(`${command.label}已完成`);
    } catch (error) {
      const message = error instanceof Error ? error.message : '操作失败';
      toast.error(message);
    }
  };

  const handleActionEvent = async (item: InboxActionItem, eventType: ActionEventType) => {
    const labels: Partial<Record<ActionEventType, string>> = {
      accepted: '已采纳',
      completed: '已完成',
      ignored: '已忽略',
      snoozed: '已设为稍后处理',
    };
    try {
      await recordActionEvent.mutateAsync({ action: item, event_type: eventType });
      toast.success(labels[eventType] || '已记录');
    } catch (error) {
      const message = error instanceof Error ? error.message : '记录行动状态失败';
      toast.error(message);
    }
  };

  const handleSwipeEnd = (item: InboxActionItem, clientX: number) => {
    const delta = clientX - touchStartX.current;
    if (Math.abs(delta) < 72) return;
    handleActionEvent(item, delta > 0 ? 'accepted' : 'ignored');
  };

  const totalCount = data?.summary.total ?? 0;
  const urgentCount = data?.summary.urgent ?? 0;
  const highCount = data?.summary.high ?? 0;
  const isAllClear = !isLoading && !isError && activeTab === 'all' && visibleItems.length === 0;
  const actionItems = activeTab === 'all' && !showLaterItems
    ? visibleItems.filter((item) => item.priority !== 'low')
    : visibleItems;
  const laterItemCount = activeTab === 'all'
    ? visibleItems.filter((item) => item.priority === 'low').length
    : 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-primary">
            <Sparkles className="h-4 w-4" />
            收件箱
          </div>
          <h1 className="text-2xl font-bold tracking-tight">{isAllClear ? '今天已清空' : '今天'}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {isAllClear ? '没有必须处理的事项。' : `${totalCount} 个待处理，按风险和截止时间排序。`}
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-sm md:justify-end">
          <div>
            <div className="text-lg font-semibold">{totalCount}</div>
            <div className="text-xs text-muted-foreground">待处理</div>
          </div>
          <div>
            <div className="text-lg font-semibold text-destructive">{urgentCount}</div>
            <div className="text-xs text-muted-foreground">紧急</div>
          </div>
          <div>
            <div className="text-lg font-semibold text-orange-600">{highCount}</div>
            <div className="text-xs text-muted-foreground">高优先级</div>
          </div>
        </div>
      </header>

      {!isLoading && !isError && items.length > 0 && <ActionInboxInsightStrip items={items} />}
      {!isLoading && !isError && items.length === 0 && <RoleGuidanceStrip role={role} />}
      {!isLoading && !isError && items.length === 0 && <AIOperatingSystemStrip />}

      <nav className="flex flex-wrap gap-2 border-b pb-3">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          const count = sourceCounts[tab.key] ?? 0;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors',
                active
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
              {count > 0 && <Badge variant={active ? 'secondary' : 'outline'}>{count}</Badge>}
            </button>
          );
        })}
      </nav>

      {isLoading && (
        <WorkLoadingState title="正在整理今日行动" description="正在合并审批、客户风险、通知和 Agent Ops。" />
      )}

      {isError && (
        <WorkErrorState
          title="行动列表加载失败"
          description="请稍后重试，或检查后端 `/api/inbox/actions` 是否可用。"
          actionLabel="重新加载"
          onAction={() => refetch()}
        />
      )}

      {!isLoading && !isError && visibleItems.length > 0 && (
        <section className="space-y-3">
          {actionItems.map((item) => {
            const meta = SOURCE_META[item.source];
            const Icon = meta.icon;
            const time = formatTime(item.due_at || item.created_at);
            const evidence = getEvidence(item).slice(0, 4);
            const riskFlags = getRiskFlags(item).slice(0, 3);
            const trustLevel = getTrustLevel(item);
            const riskScore = typeof item.metadata?.risk_score === 'number' ? item.metadata.risk_score : undefined;
            const expanded = expandedItemId === item.id;
            const primaryCommand = item.actions.find((command) => command.variant === 'primary') || item.actions[0];
            const secondaryCommands = item.actions.filter((command) => command.id !== primaryCommand?.id);
            const showPriority = item.priority === 'urgent' || item.priority === 'high';
            return (
              <article
                key={item.id}
                onTouchStart={(event) => {
                  touchStartX.current = event.touches[0]?.clientX ?? 0;
                }}
                onTouchEnd={(event) => {
                  const clientX = event.changedTouches[0]?.clientX;
                  if (typeof clientX === 'number') handleSwipeEnd(item, clientX);
                }}
                className="rounded-lg border bg-card p-4 shadow-sm transition-colors hover:bg-accent/30"
              >
                <div className="flex gap-3">
                  <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-lg', meta.tone)}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline">{meta.label}</Badge>
                          {showPriority && (
                            <Badge variant="outline" className={PRIORITY_CLASS[item.priority]}>
                              {PRIORITY_LABEL[item.priority]}
                            </Badge>
                          )}
                          {time && (
                            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                              <Clock className="h-3.5 w-3.5" />
                              {time}
                            </span>
                          )}
                        </div>
                        <h2 className="mt-2 text-base font-semibold leading-snug">{item.title}</h2>
                        {item.description && (
                          <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">{item.description}</p>
                        )}
                        {item.reason && <p className="mt-1 line-clamp-1 text-xs text-primary">{item.reason}</p>}
                      </div>

                      <div className="flex shrink-0 flex-wrap gap-2 md:justify-end">
                        {primaryCommand && (
                          <Button
                            key={primaryCommand.id}
                            size="sm"
                            variant={
                              primaryCommand.variant === 'danger'
                                ? 'destructive'
                                : primaryCommand.variant === 'primary'
                                  ? 'default'
                                  : 'outline'
                            }
                            onClick={() => handleCommand(item, primaryCommand)}
                          >
                            {primaryCommand.label}
                            {primaryCommand.kind === 'navigate' && <ExternalLink className="ml-1.5 h-3.5 w-3.5" />}
                          </Button>
                        )}
                        <Button
                          data-testid={`inbox-action-accept-${item.id}`}
                          size="sm"
                          variant="ghost"
                          onClick={() => handleActionEvent(item, 'accepted')}
                        >
                          <CheckCircle2 className="mr-1.5 h-4 w-4" />
                          采纳
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setExpandedItemId(expanded ? null : item.id)}
                        >
                          {expanded ? '收起' : '详情'}
                          {expanded ? (
                            <ChevronDown className="ml-1.5 h-3.5 w-3.5" />
                          ) : (
                            <ChevronRight className="ml-1.5 h-3.5 w-3.5" />
                          )}
                        </Button>
                      </div>
                    </div>

                    {expanded && (
                      <div className="mt-3 space-y-3 rounded-lg border bg-muted/20 p-3">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span>AI 判断</span>
                          <AITrustBadge level={trustLevel} score={riskScore ? 100 - riskScore : undefined} />
                        </div>

                        {(evidence.length > 0 || riskFlags.length > 0) && (
                          <div className="grid gap-2 text-xs md:grid-cols-2">
                            {evidence.length > 0 && (
                              <div className="space-y-1.5">
                                <div className="font-medium text-foreground">AI 证据链</div>
                                {evidence.map((entry) => (
                                  <div key={`${item.id}-${entry.label}`} className="flex gap-2">
                                    <span className="shrink-0 text-muted-foreground">{entry.label}:</span>
                                    <span className="min-w-0 truncate text-foreground">{entry.value}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                            {riskFlags.length > 0 && (
                              <div className="space-y-1.5">
                                <div className="font-medium text-foreground">风险</div>
                                {riskFlags.map((flag) => (
                                  <div key={`${item.id}-${flag}`} className="flex gap-2">
                                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                                    <span className="text-muted-foreground">{flag}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        <div className="flex flex-wrap gap-2">
                          {secondaryCommands.map((command) => (
                            <Button
                              key={command.id}
                              size="sm"
                              variant={command.variant === 'danger' ? 'destructive' : 'outline'}
                              onClick={() => handleCommand(item, command)}
                            >
                              {command.label}
                              {command.kind === 'navigate' && <ExternalLink className="ml-1.5 h-3.5 w-3.5" />}
                            </Button>
                          ))}
                          <Button size="sm" variant="ghost" onClick={() => handleActionEvent(item, 'completed')}>
                            <CheckCircle2 className="mr-1.5 h-4 w-4" />
                            标记完成
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => handleActionEvent(item, 'ignored')}>
                            忽略
                          </Button>
                        </div>
                      </div>
                    )}

                    <div className="mt-2 text-[11px] text-muted-foreground md:hidden">右滑采纳，左滑忽略</div>
                  </div>
                </div>
              </article>
            );
          })}

          {activeTab === 'all' && laterItemCount > 0 && (
            <div className="flex items-center justify-between rounded-lg border bg-muted/20 px-3 py-2 text-sm">
              <span className="text-muted-foreground">
                {showLaterItems ? '已显示稍后事项' : `${laterItemCount} 个低优先级事项已收起`}
              </span>
              <Button size="sm" variant="ghost" onClick={() => setShowLaterItems((value) => !value)}>
                {showLaterItems ? '收起稍后' : '查看稍后'}
              </Button>
            </div>
          )}
        </section>
      )}

      {!isLoading && !isError && visibleItems.length === 0 && (
        <WorkEmptyState
          icon={<CheckCircle2 className="h-6 w-6" />}
          title={activeTab === 'all' ? '今天已清空' : '这个分类没有待办'}
          description={activeTab === 'all' ? 'AI 可以帮你生成下一步工作计划。' : '切回全部行动查看其他事项。'}
          actionLabel={activeTab === 'all' ? '生成今日计划' : '查看全部行动'}
          onAction={() => {
            if (activeTab === 'all') {
              triggerAI('请根据我的收件箱、客户风险和审批情况，生成一份今天的工作计划。');
              return;
            }
            setActiveTab('all');
          }}
        />
      )}
    </div>
  );
}

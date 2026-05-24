import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { httpClient } from '@/lib/httpClient';

export type ActionPriority = 'urgent' | 'high' | 'medium' | 'low';
export type ActionSource = 'approval' | 'notification' | 'crm' | 'system';
export type ActionEventType =
  | 'viewed'
  | 'accepted'
  | 'completed'
  | 'ignored'
  | 'snoozed'
  | 'command_executed';

export interface InboxActionCommand {
  id: string;
  label: string;
  kind: 'api' | 'navigate';
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  method?: string | null;
  url?: string | null;
  payload?: Record<string, unknown> | null;
  navigate_to?: string | null;
}

export interface InboxActionItem {
  id: string;
  source: ActionSource;
  source_id: string;
  type: string;
  title: string;
  description?: string | null;
  reason?: string | null;
  priority: ActionPriority;
  status: 'open' | 'done' | 'archived';
  due_at?: string | null;
  created_at?: string | null;
  action_url?: string | null;
  actions: InboxActionCommand[];
  metadata: Record<string, unknown>;
}

export interface InboxActionSummary {
  total: number;
  urgent: number;
  high: number;
  by_source: Record<ActionSource, number>;
}

export interface InboxActionEventPayload {
  action: InboxActionItem;
  event_type: ActionEventType;
  comment?: string;
  metadata?: Record<string, unknown>;
}

interface InboxActionResponse {
  items: InboxActionItem[];
  summary: InboxActionSummary;
}

export interface InboxAnalyticsSummary {
  total_events: number;
  accepted: number;
  completed: number;
  ignored: number;
  snoozed: number;
  completion_rate: number;
  acceptance_rate: number;
  ignored_rate: number;
  open_high_risk: number;
  unique_actors: number;
}

export interface InboxAnalyticsSource {
  total: number;
  accepted: number;
  completed: number;
  ignored: number;
  snoozed: number;
  command_executed: number;
}

export interface InboxAnalyticsEvent {
  id?: string;
  action_id: string;
  source: ActionSource;
  event_type: ActionEventType;
  created_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface InboxAnalyticsResponse {
  window_days: number;
  summary: InboxAnalyticsSummary;
  by_source: Partial<Record<ActionSource, InboxAnalyticsSource>>;
  stale_open_actions: InboxActionItem[];
  recent_events: InboxAnalyticsEvent[];
}

export function useInboxActions(limit = 50) {
  return useQuery({
    queryKey: ['inbox-actions', limit],
    queryFn: async () => {
      const response = await httpClient.get('/api/inbox/actions', {
        params: { limit },
      });
      return response.data?.data as InboxActionResponse;
    },
    refetchInterval: 120_000,
  });
}

export function useInboxAnalytics(days = 30) {
  return useQuery({
    queryKey: ['inbox-analytics', days],
    queryFn: async () => {
      const response = await httpClient.get('/api/inbox/analytics', {
        params: { days },
      });
      return response.data?.data as InboxAnalyticsResponse;
    },
    refetchInterval: 180_000,
  });
}

export function useExecuteInboxAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (command: InboxActionCommand) => {
      if (command.kind !== 'api' || !command.url) return null;
      const method = (command.method || 'POST').toLowerCase();
      const response = await httpClient.request({
        method,
        url: command.url,
        data: command.payload || {},
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbox-actions'] });
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['notification-center'] });
      queryClient.invalidateQueries({ queryKey: ['notification-unread-count'] });
    },
  });
}

export function useRecordInboxActionEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      action,
      event_type,
      comment,
      metadata,
    }: InboxActionEventPayload) => {
      const response = await httpClient.post(
        `/api/inbox/actions/${encodeURIComponent(action.id)}/events`,
        {
          action_id: action.id,
          source: action.source,
          source_id: action.source_id,
          event_type,
          comment,
          metadata: {
            title: action.title,
            priority: action.priority,
            action_type: action.type,
            ...(metadata || {}),
          },
        },
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inbox-actions'] });
    },
  });
}

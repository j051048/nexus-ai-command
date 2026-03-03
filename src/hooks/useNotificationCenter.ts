import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';

// ─── Types ──────────────────────────────────────────────────

export interface NotificationItem {
  id: string;
  user_id: string;
  organization_id?: string;
  title: string;
  content?: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'approval' | 'system';
  action_url?: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationPreferences {
  user_id: string;
  email_enabled: boolean;
  push_enabled: boolean;
  im_enabled: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  categories: Record<string, boolean>;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

// ─── Constants ──────────────────────────────────────────────

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// ─── Auth Fetch Helper ──────────────────────────────────────

async function authFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  let baseUrl = API_BASE_URL;
  if (!baseUrl.startsWith('http')) {
    baseUrl = baseUrl.includes('localhost') ? `http://${baseUrl}` : `https://${baseUrl}`;
  }
  const cleanBase = baseUrl.replace(/\/$/, '');
  const cleanEndpoint = url.startsWith('/') ? url.slice(1) : url;
  const fullUrl = `${cleanBase}/${cleanEndpoint}`;

  const response = await fetch(fullUrl, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string>),
    },
  });

  if (!response.ok) {
    let errorMessage = `请求失败 (${response.status})`;
    try {
      const errorData = await response.json();
      if (errorData.error?.message) errorMessage = errorData.error.message;
      else if (typeof errorData.detail === 'string') errorMessage = errorData.detail;
    } catch {
      // ignore
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

// ─── Hooks ──────────────────────────────────────────────────

/**
 * Fetch notification list from the notification center API
 */
export function useNotificationCenter(options?: {
  unreadOnly?: boolean;
  type?: string;
  limit?: number;
}) {
  const { unreadOnly = false, type, limit = 50 } = options ?? {};

  return useQuery({
    queryKey: ['notification-center', unreadOnly, type, limit],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (unreadOnly) params.set('unread_only', 'true');
      if (type) params.set('type', type);
      params.set('limit', String(limit));

      const result = await authFetch<ApiResponse<NotificationItem[]>>(
        `api/notifications?${params.toString()}`
      );
      return result.data ?? [];
    },
    refetchInterval: 300_000, // 5min fallback, WebSocket is primary
  });
}

/**
 * Get unread notification count (for badge)
 */
export function useUnreadCount() {
  return useQuery({
    queryKey: ['notification-unread-count'],
    queryFn: async () => {
      const result = await authFetch<ApiResponse<{ unread_count: number }>>(
        'api/notifications/unread-count'
      );
      return result.data?.unread_count ?? 0;
    },
    refetchInterval: 300_000, // 5min fallback, WebSocket is primary
  });
}

/**
 * Mark specific notifications as read
 */
export function useMarkRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (notificationIds: string[]) => {
      const result = await authFetch<ApiResponse<{ marked_count: number }>>(
        'api/notifications/mark-read',
        {
          method: 'POST',
          body: JSON.stringify({ notification_ids: notificationIds }),
        }
      );
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-center'] });
      queryClient.invalidateQueries({ queryKey: ['notification-unread-count'] });
    },
  });
}

/**
 * Mark all notifications as read
 */
export function useMarkAllRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const result = await authFetch<ApiResponse<{ marked_count: number }>>(
        'api/notifications/mark-all-read',
        { method: 'POST' }
      );
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-center'] });
      queryClient.invalidateQueries({ queryKey: ['notification-unread-count'] });
    },
  });
}

/**
 * Get notification preferences
 */
export function useNotificationPreferences() {
  return useQuery({
    queryKey: ['notification-preferences'],
    queryFn: async () => {
      const result = await authFetch<ApiResponse<NotificationPreferences>>(
        'api/notifications/preferences'
      );
      return result.data;
    },
  });
}

/**
 * Update notification preferences
 */
export function useUpdateNotificationPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (preferences: Partial<NotificationPreferences>) => {
      const result = await authFetch<ApiResponse<NotificationPreferences>>(
        'api/notifications/preferences',
        {
          method: 'PUT',
          body: JSON.stringify(preferences),
        }
      );
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-preferences'] });
    },
  });
}

/**
 * usePageSuggestions — 管理页面级 AI 主动建议的请求和状态
 */

import { useState, useEffect, useCallback } from 'react';
import { aiClient } from '@/api/aiClient';

export interface PageSuggestion {
  id: string;
  title: string;
  description: string;
  actionLabel: string;
  actionType: 'navigate' | 'chat' | 'execute';
  actionPayload: string;
  priority: 'high' | 'medium' | 'low';
  icon?: string;
}

interface UsePageSuggestionsOptions {
  page: string;
  context?: Record<string, unknown>;
  enabled?: boolean;
}

interface UsePageSuggestionsReturn {
  suggestions: PageSuggestion[];
  isLoading: boolean;
  error: string | null;
  dismiss: (id: string) => void;
  dismissAll: () => void;
  refresh: () => void;
}

const DISMISSED_KEY = 'nexus:dismissed-suggestions';

function loadDismissed(): Set<string> {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function saveDismissed(dismissed: Set<string>) {
  localStorage.setItem(DISMISSED_KEY, JSON.stringify([...dismissed]));
}

export function usePageSuggestions({
  page,
  context = {},
  enabled = true,
}: UsePageSuggestionsOptions): UsePageSuggestionsReturn {
  const [suggestions, setSuggestions] = useState<PageSuggestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<Set<string>>(loadDismissed);

  const fetchSuggestions = useCallback(async () => {
    if (!enabled) return;
    setIsLoading(true);
    setError(null);

    try {
      const data = await aiClient.fetch<{ suggestions?: PageSuggestion[] }>(
        'api/ai/page-suggestions',
        {
          method: 'POST',
          body: JSON.stringify({ page, context }),
          _silentError: true,
        },
      );
      const items: PageSuggestion[] = data?.suggestions ?? [];
      setSuggestions(items.filter((s) => !dismissed.has(s.id)));
    } catch {
      // 后端未实现或网络错误时使用回退建议
      setSuggestions(getFallbackSuggestions(page).filter((s) => !dismissed.has(s.id)));
    } finally {
      setIsLoading(false);
    }
  }, [page, context, enabled, dismissed]);

  useEffect(() => {
    fetchSuggestions();
  }, [page]);

  const dismiss = useCallback((id: string) => {
    setDismissed((prev) => {
      const next = new Set(prev);
      next.add(id);
      saveDismissed(next);
      return next;
    });
    setSuggestions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const dismissAll = useCallback(() => {
    setDismissed((prev) => {
      const next = new Set(prev);
      suggestions.forEach((s) => next.add(s.id));
      saveDismissed(next);
      return next;
    });
    setSuggestions([]);
  }, [suggestions]);

  const refresh = useCallback(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  return { suggestions, isLoading, error, dismiss, dismissAll, refresh };
}

/** 后端不可用时的回退建议 */
function getFallbackSuggestions(page: string): PageSuggestion[] {
  const fallbackMap: Record<string, PageSuggestion[]> = {
    sales: [
      {
        id: 'sales-follow-up',
        title: 'AI 发现 3 个高价值线索需要跟进',
        description: '有 3 条线索超过 7 天未跟进，建议尽快联系以免错过最佳时机。',
        actionLabel: '查看线索',
        actionType: 'navigate',
        actionPayload: '/sales?tab=leads&filter=overdue',
        priority: 'high',
      },
      {
        id: 'sales-forecast',
        title: '本月销售预测低于目标 15%',
        description: 'AI 分析当前漏斗数据，预计本月完成率约 85%，建议加大拓客力度。',
        actionLabel: '查看预测',
        actionType: 'chat',
        actionPayload: '分析本月销售预测和差距',
        priority: 'medium',
      },
    ],
    dashboard: [
      {
        id: 'dashboard-anomaly',
        title: '检测到异常数据波动',
        description: '昨日客户退单率上升 20%，可能需要关注产品质量或服务问题。',
        actionLabel: 'AI 分析',
        actionType: 'chat',
        actionPayload: '分析昨日退单率上升的原因',
        priority: 'high',
      },
      {
        id: 'dashboard-report',
        title: '周报即将到期',
        description: '本周日报已填写 3/5 天，系统可自动汇总生成周报。',
        actionLabel: '生成周报',
        actionType: 'execute',
        actionPayload: 'generate-weekly-report',
        priority: 'low',
      },
    ],
    crm: [
      {
        id: 'crm-birthday',
        title: '2 位重要客户即将生日',
        description: '建议提前安排生日祝福，维护客户关系。',
        actionLabel: '查看详情',
        actionType: 'navigate',
        actionPayload: '/crm?filter=upcoming-birthday',
        priority: 'medium',
      },
    ],
  };

  return fallbackMap[page] ?? [];
}

export default usePageSuggestions;

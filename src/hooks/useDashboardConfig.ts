import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { httpClient } from '@/lib/httpClient';

// ─── 类型定义 ──────────────────────────────────────────────

export type CardType = 'kpi' | 'bar' | 'pie' | 'line' | 'approval_stats' | 'leaderboard';

export interface DashboardCardConfig {
  id: string;
  type: CardType;
  title: string;
  dataSource: string;
  /** 列跨度 1 或 2 */
  colSpan?: 1 | 2;
}

export interface DashboardConfig {
  cards: DashboardCardConfig[];
}

// ─── 默认配置 ──────────────────────────────────────────────

export const CARD_TYPE_OPTIONS: { value: CardType; label: string }[] = [
  { value: 'kpi', label: 'KPI 数字' },
  { value: 'bar', label: '柱状图' },
  { value: 'pie', label: '饼图' },
  { value: 'line', label: '折线图' },
  { value: 'approval_stats', label: '审批统计' },
  { value: 'leaderboard', label: '排行榜' },
];

export const DATA_SOURCE_OPTIONS: { value: string; label: string }[] = [
  { value: 'sales', label: '销售数据' },
  { value: 'approval', label: '审批数据' },
  { value: 'project', label: '项目数据' },
  { value: 'hr', label: '人事数据' },
  { value: 'finance', label: '财务数据' },
  { value: 'performance', label: '绩效数据' },
];

const DEFAULT_CONFIG: DashboardConfig = {
  cards: [
    { id: '1', type: 'kpi', title: '本月销售额', dataSource: 'sales' },
    { id: '2', type: 'kpi', title: '待审批数', dataSource: 'approval' },
    { id: '3', type: 'kpi', title: '活跃项目', dataSource: 'project' },
    { id: '4', type: 'line', title: '销售趋势', dataSource: 'sales', colSpan: 2 },
    { id: '5', type: 'pie', title: '审批分布', dataSource: 'approval' },
    { id: '6', type: 'leaderboard', title: '销售排行', dataSource: 'sales' },
  ],
};

const STORAGE_KEY = 'nexus-custom-dashboard-config';

// ─── localStorage helpers (fast cache) ──────────────────────

function readLocalConfig(): DashboardConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DashboardConfig) : DEFAULT_CONFIG;
  } catch {
    return DEFAULT_CONFIG;
  }
}

function writeLocalConfig(config: DashboardConfig) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  } catch {
    // ignore quota errors
  }
}

// ─── Hook ──────────────────────────────────────────────────

export function useDashboardConfig() {
  const { user, profile } = useAuth();
  const userId = user?.id;
  const orgId = profile?.organization_id;
  const queryClient = useQueryClient();

  // Local state initialised from localStorage for instant render
  const [config, setConfigLocal] = useState<DashboardConfig>(readLocalConfig);

  // Debounce ref for saving to DB
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Fetch from API ──────────────────────────────────
  const { data: dbConfig } = useQuery({
    queryKey: ['dashboard-config', userId],
    queryFn: async () => {
      const response = await httpClient.get('/api/system/dashboard-configs');
      return response.data?.config?.config_json || null;
    },
    enabled: !!userId,
    staleTime: 60_000,
  });

  // Reconcile: when DB config arrives, use it (DB is source of truth)
  useEffect(() => {
    if (dbConfig) {
      setConfigLocal(dbConfig);
      writeLocalConfig(dbConfig);
    }
  }, [dbConfig]);

  // ── Save mutation ────────────────────────────────────────
  const saveMutation = useMutation({
    mutationFn: async (newConfig: DashboardConfig) => {
      if (!userId) return;
      await httpClient.post('/api/system/dashboard-configs', { config: newConfig });
    },
    onError: (err) => {
      console.warn('Dashboard config save to DB failed:', err);
    },
  });

  // ── Debounced persist ────────────────────────────────────
  const persistConfig = useCallback(
    (newConfig: DashboardConfig) => {
      // Immediately write to localStorage
      writeLocalConfig(newConfig);

      // Debounce the DB save (500ms)
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        saveMutation.mutate(newConfig);
      }, 500);
    },
    [saveMutation],
  );

  // Wrapper that updates local state + triggers persistence
  const setConfig = useCallback(
    (value: DashboardConfig | ((prev: DashboardConfig) => DashboardConfig)) => {
      setConfigLocal((prev) => {
        const next = typeof value === 'function' ? value(prev) : value;
        persistConfig(next);
        return next;
      });
    },
    [persistConfig],
  );

  // ── CRUD helpers ─────────────────────────────────────────
  const addCard = useCallback(
    (card: Omit<DashboardCardConfig, 'id'>) => {
      const id = `card-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setConfig((prev) => ({
        ...prev,
        cards: [...prev.cards, { ...card, id }],
      }));
    },
    [setConfig],
  );

  const removeCard = useCallback(
    (cardId: string) => {
      setConfig((prev) => ({
        ...prev,
        cards: prev.cards.filter((c) => c.id !== cardId),
      }));
    },
    [setConfig],
  );

  const updateCard = useCallback(
    (cardId: string, updates: Partial<DashboardCardConfig>) => {
      setConfig((prev) => ({
        ...prev,
        cards: prev.cards.map((c) => (c.id === cardId ? { ...c, ...updates } : c)),
      }));
    },
    [setConfig],
  );

  const resetConfig = useCallback(() => {
    setConfig(DEFAULT_CONFIG);
  }, [setConfig]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  return {
    config,
    setConfig,
    addCard,
    removeCard,
    updateCard,
    resetConfig,
    isSaving: saveMutation.isPending,
  };
}

import { useState, useCallback, useEffect } from 'react';

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

// ─── useLocalStorage ──────────────────────────────────────

function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T | ((prev: T) => T)) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = localStorage.getItem(key);
      return item ? (JSON.parse(item) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      setStoredValue((prev) => {
        const nextValue = typeof value === 'function' ? (value as (prev: T) => T)(prev) : value;
        try {
          localStorage.setItem(key, JSON.stringify(nextValue));
        } catch {
          // ignore quota errors
        }
        return nextValue;
      });
    },
    [key],
  );

  return [storedValue, setValue];
}

// ─── Hook ──────────────────────────────────────────────────

export function useDashboardConfig() {
  const [config, setConfig] = useLocalStorage<DashboardConfig>(STORAGE_KEY, DEFAULT_CONFIG);

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

  return {
    config,
    setConfig,
    addCard,
    removeCard,
    updateCard,
    resetConfig,
  };
}

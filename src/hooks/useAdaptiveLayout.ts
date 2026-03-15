/**
 * useAdaptiveLayout — 基于用户行为驱动的自适应布局
 * 跟踪用户访问频率，动态排序菜单项，按角色推荐快捷操作
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  loadFrequencyData,
  saveFrequencyData,
  loadLayoutPreferences,
  saveLayoutPreferences,
  type FrequencyData,
  type LayoutPreferences,
} from '@/services/layoutPreferenceService';

type AppRole = 'boss' | 'manager' | 'employee' | 'founder' | 'ai_assistant';

interface MenuItem {
  href: string;
  label: string;
  group: string;
  [key: string]: unknown;
}

interface QuickAction {
  id: string;
  label: string;
  href: string;
  icon?: string;
}

interface UseAdaptiveLayoutReturn {
  /** 记录一次页面访问 */
  trackPageVisit: (href: string) => void;
  /** 根据频率排序菜单项（同组内排序） */
  getSortedMenuItems: <T extends MenuItem>(items: T[]) => T[];
  /** 获取角色相关的快捷操作 */
  getQuickActions: (userRole: AppRole) => QuickAction[];
  /** 原始频率数据 */
  frequencyData: FrequencyData;
  /** 布局偏好 */
  preferences: LayoutPreferences;
  /** 更新布局偏好 */
  updatePreferences: (partial: Partial<LayoutPreferences>) => void;
}

/** 按角色预设的快捷操作 */
const roleQuickActions: Record<string, QuickAction[]> = {
  boss: [
    { id: 'boss-dashboard', label: '总控中心', href: '/boss-dashboard' },
    { id: 'boss-approval', label: '快速审批', href: '/approval' },
    { id: 'boss-reports', label: '数据报表', href: '/reports' },
    { id: 'boss-team', label: '团队洞察', href: '/employees' },
  ],
  founder: [
    { id: 'founder-dashboard', label: '总控中心', href: '/boss-dashboard' },
    { id: 'founder-settings', label: '企业设置', href: '/company-settings' },
    { id: 'founder-reports', label: '经营报表', href: '/reports' },
    { id: 'founder-org', label: '组织架构', href: '/org-chart' },
  ],
  manager: [
    { id: 'mgr-dashboard', label: '战绩中心', href: '/dashboard' },
    { id: 'mgr-team', label: '团队管理', href: '/employees' },
    { id: 'mgr-approval', label: '审批中心', href: '/approval' },
    { id: 'mgr-sales', label: '销售管理', href: '/sales' },
  ],
  employee: [
    { id: 'emp-dashboard', label: '战绩中心', href: '/dashboard' },
    { id: 'emp-sales', label: '销售管理', href: '/sales' },
    { id: 'emp-oa', label: 'OA办公', href: '/oa' },
    { id: 'emp-inbox', label: '待办中心', href: '/inbox' },
  ],
  ai_assistant: [
    { id: 'ai-dashboard', label: '战绩中心', href: '/dashboard' },
    { id: 'ai-vmd', label: '虚拟市场部', href: '/vmd' },
  ],
};

export function useAdaptiveLayout(): UseAdaptiveLayoutReturn {
  const [frequencyData, setFrequencyData] = useState<FrequencyData>(loadFrequencyData);
  const [preferences, setPreferences] = useState<LayoutPreferences>(loadLayoutPreferences);

  // 持久化频率数据变更
  useEffect(() => {
    saveFrequencyData(frequencyData);
  }, [frequencyData]);

  useEffect(() => {
    saveLayoutPreferences(preferences);
  }, [preferences]);

  const trackPageVisit = useCallback((href: string) => {
    const cleanHref = href.replace(/^\//, '').split('?')[0];
    setFrequencyData((prev) => {
      const count = (prev[cleanHref]?.count ?? 0) + 1;
      return {
        ...prev,
        [cleanHref]: {
          count,
          lastVisited: Date.now(),
        },
      };
    });
  }, []);

  const getSortedMenuItems = useCallback(
    <T extends MenuItem>(items: T[]): T[] => {
      // 按组分组，组内按访问频率降序排序
      const grouped = new Map<string, T[]>();
      for (const item of items) {
        const group = item.group;
        if (!grouped.has(group)) grouped.set(group, []);
        grouped.get(group)!.push(item);
      }

      const result: T[] = [];
      for (const [, groupItems] of grouped) {
        const sorted = [...groupItems].sort((a, b) => {
          const aHref = a.href.replace(/^\//, '').split('?')[0];
          const bHref = b.href.replace(/^\//, '').split('?')[0];
          const aCount = frequencyData[aHref]?.count ?? 0;
          const bCount = frequencyData[bHref]?.count ?? 0;
          return bCount - aCount;
        });
        result.push(...sorted);
      }
      return result;
    },
    [frequencyData],
  );

  const getQuickActions = useCallback(
    (userRole: AppRole): QuickAction[] => {
      const baseActions = roleQuickActions[userRole] ?? roleQuickActions.employee;

      // 根据频率数据调整排序：把用户最常用的放前面
      const sorted = [...baseActions].sort((a, b) => {
        const aHref = a.href.replace(/^\//, '');
        const bHref = b.href.replace(/^\//, '');
        const aCount = frequencyData[aHref]?.count ?? 0;
        const bCount = frequencyData[bHref]?.count ?? 0;
        return bCount - aCount;
      });

      return sorted;
    },
    [frequencyData],
  );

  const updatePreferences = useCallback((partial: Partial<LayoutPreferences>) => {
    setPreferences((prev) => ({ ...prev, ...partial }));
  }, []);

  return {
    trackPageVisit,
    getSortedMenuItems,
    getQuickActions,
    frequencyData,
    preferences,
    updatePreferences,
  };
}

export { type AppRole, type MenuItem, type QuickAction };
export default useAdaptiveLayout;

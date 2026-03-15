/**
 * layoutPreferenceService — 保存/加载用户布局偏好与页面访问频率
 * 支持 localStorage 持久化 + 可选后端持久化
 */

import { aiClient } from '@/api/aiClient';

// ─── Types ──────────────────────────────────────────────────

export interface FrequencyEntry {
  count: number;
  lastVisited: number; // timestamp
}

/** 键为页面 href（不含前导 /），值为访问统计 */
export type FrequencyData = Record<string, FrequencyEntry>;

export interface LayoutPreferences {
  sidebarCollapsed: boolean;
  favoritePages: string[];
  dashboardWidgetOrder: string[];
  theme?: 'light' | 'dark' | 'system';
}

// ─── Storage Keys ───────────────────────────────────────────

const FREQUENCY_KEY = 'nexus:page-frequency';
const PREFERENCES_KEY = 'nexus:layout-preferences';

// ─── Default Values ─────────────────────────────────────────

const DEFAULT_PREFERENCES: LayoutPreferences = {
  sidebarCollapsed: false,
  favoritePages: [],
  dashboardWidgetOrder: [],
};

// ─── localStorage Helpers ───────────────────────────────────

export function loadFrequencyData(): FrequencyData {
  try {
    const raw = localStorage.getItem(FREQUENCY_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function saveFrequencyData(data: FrequencyData): void {
  try {
    localStorage.setItem(FREQUENCY_KEY, JSON.stringify(data));
  } catch {
    // localStorage 可能已满，静默忽略
  }
}

export function loadLayoutPreferences(): LayoutPreferences {
  try {
    const raw = localStorage.getItem(PREFERENCES_KEY);
    return raw ? { ...DEFAULT_PREFERENCES, ...JSON.parse(raw) } : { ...DEFAULT_PREFERENCES };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export function saveLayoutPreferences(prefs: LayoutPreferences): void {
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(prefs));
  } catch {
    // 静默忽略
  }
}

// ─── 页面访问频率统计 ───────────────────────────────────────

/**
 * 记录一次页面访问（纯 localStorage 版本，不依赖 hook）
 */
export function recordPageVisit(href: string): void {
  const cleanHref = href.replace(/^\//, '').split('?')[0];
  const data = loadFrequencyData();
  const entry = data[cleanHref];
  data[cleanHref] = {
    count: (entry?.count ?? 0) + 1,
    lastVisited: Date.now(),
  };
  saveFrequencyData(data);
}

/**
 * 获取访问最频繁的前 N 个页面
 */
export function getTopPages(n: number = 5): Array<{ href: string } & FrequencyEntry> {
  const data = loadFrequencyData();
  return Object.entries(data)
    .map(([href, entry]) => ({ href, ...entry }))
    .sort((a, b) => b.count - a.count)
    .slice(0, n);
}

/**
 * 清除频率数据（用于 "重置布局" 功能）
 */
export function clearFrequencyData(): void {
  localStorage.removeItem(FREQUENCY_KEY);
}

export function clearLayoutPreferences(): void {
  localStorage.removeItem(PREFERENCES_KEY);
}

// ─── 可选后端持久化 ─────────────────────────────────────────

/**
 * 将本地偏好同步到后端（可选，如后端 API 已就绪）
 * 返回 true 表示同步成功
 */
export async function syncPreferencesToBackend(
  userId: string,
  preferences: LayoutPreferences,
  frequencyData: FrequencyData,
): Promise<boolean> {
  try {
    await aiClient.put('api/user/layout-preferences', {
      user_id: userId,
      preferences,
      frequency_data: frequencyData,
    }, { _silentError: true });
    return true;
  } catch {
    return false;
  }
}

/**
 * 从后端加载偏好（登录后同步）
 */
export async function loadPreferencesFromBackend(
  userId: string,
): Promise<{ preferences: LayoutPreferences; frequencyData: FrequencyData } | null> {
  try {
    const { data } = await aiClient.get(`api/user/layout-preferences?user_id=${userId}`, {
      _silentError: true,
    });
    return {
      preferences: { ...DEFAULT_PREFERENCES, ...data.preferences },
      frequencyData: data.frequency_data ?? {},
    };
  } catch {
    return null;
  }
}

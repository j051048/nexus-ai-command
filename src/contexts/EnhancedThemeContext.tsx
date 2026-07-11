/* eslint-disable react-refresh/only-export-components */
/**
 * P2 UX Enhancement: Enhanced Theme Context
 * 增强版主题系统 - 支持自定义颜色、多主题预设
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  ReactNode,
} from 'react';

// ==================== 类型定义 ====================

export type ThemeMode = 'light' | 'dark' | 'system';

export interface ThemeColors {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  foreground: string;
  muted: string;
  border: string;
}

export interface ThemePreset {
  id: string;
  name: string;
  description?: string;
  mode: 'light' | 'dark';
  colors: Partial<ThemeColors>;
}

export interface ThemeSettings {
  mode: ThemeMode;
  preset: string;
  customColors: Partial<ThemeColors>;
  fontSize: 'sm' | 'base' | 'lg';
  radius: 'none' | 'sm' | 'md' | 'lg' | 'full';
  reducedMotion: boolean;
}

interface EnhancedThemeContextValue {
  // 当前状态
  mode: ThemeMode;
  resolvedMode: 'light' | 'dark';
  preset: string;
  settings: ThemeSettings;
  
  // 操作方法
  setMode: (mode: ThemeMode) => void;
  toggleMode: () => void;
  setPreset: (presetId: string) => void;
  setCustomColor: (key: keyof ThemeColors, value: string) => void;
  setFontSize: (size: ThemeSettings['fontSize']) => void;
  setRadius: (radius: ThemeSettings['radius']) => void;
  setReducedMotion: (reduced: boolean) => void;
  resetToDefaults: () => void;
  
  // 预设列表
  presets: ThemePreset[];
}

// ==================== 预设主题 ====================

const themePresets: ThemePreset[] = [
  {
    id: 'default-dark',
    name: '默认深色',
    description: '赛博朋克风格',
    mode: 'dark',
    colors: {
      primary: '211 100% 50%',
      accent: '142 69% 50%',
    },
  },
  {
    id: 'default-light',
    name: '默认浅色',
    description: '专业简洁',
    mode: 'light',
    colors: {
      primary: '217 91% 50%',
      accent: '142 69% 45%',
    },
  },
  {
    id: 'ocean',
    name: '海洋',
    description: '清新蓝色调',
    mode: 'dark',
    colors: {
      primary: '200 100% 50%',
      accent: '180 70% 45%',
    },
  },
  {
    id: 'forest',
    name: '森林',
    description: '自然绿色调',
    mode: 'dark',
    colors: {
      primary: '150 80% 40%',
      accent: '120 60% 50%',
    },
  },
  {
    id: 'sunset',
    name: '日落',
    description: '温暖橙色调',
    mode: 'dark',
    colors: {
      primary: '25 95% 55%',
      accent: '45 100% 50%',
    },
  },
  {
    id: 'purple',
    name: '紫罗兰',
    description: '优雅紫色调',
    mode: 'dark',
    colors: {
      primary: '270 80% 60%',
      accent: '300 70% 50%',
    },
  },
  {
    id: 'rose',
    name: '玫瑰',
    description: '柔和粉色调',
    mode: 'light',
    colors: {
      primary: '350 80% 55%',
      accent: '330 70% 50%',
    },
  },
  {
    id: 'monochrome',
    name: '单色',
    description: '极简黑白',
    mode: 'dark',
    colors: {
      primary: '0 0% 100%',
      accent: '0 0% 70%',
    },
  },
];

// ==================== 默认设置 ====================

const defaultSettings: ThemeSettings = {
  mode: 'light',
  preset: 'default-light',
  customColors: {},
  fontSize: 'base',
  radius: 'lg',
  reducedMotion: false,
};

// ==================== 存储键 ====================

const STORAGE_KEY = 'nexus-theme-settings';

// ==================== Context ====================

const EnhancedThemeContext = createContext<EnhancedThemeContextValue | undefined>(undefined);

export function EnhancedThemeProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<ThemeSettings>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        try {
          return { ...defaultSettings, ...JSON.parse(saved) };
        } catch {
          return defaultSettings;
        }
      }
    }
    return defaultSettings;
  });

  const [systemMode, setSystemMode] = useState<'light' | 'dark'>('dark');

  // 监听系统主题变化
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    setSystemMode(mediaQuery.matches ? 'dark' : 'light');

    const handler = (e: MediaQueryListEvent) => {
      setSystemMode(e.matches ? 'dark' : 'light');
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  // 解析后的模式
  const resolvedMode = useMemo(
    () => (settings.mode === 'system' ? systemMode : settings.mode),
    [settings.mode, systemMode]
  );

  // 保存设置到 localStorage
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  // 应用主题到 DOM
  useEffect(() => {
    const root = document.documentElement;
    
    // 设置深色/浅色模式
    root.classList.remove('light', 'dark');
    root.classList.add(resolvedMode);

    // 应用预设颜色
    const preset = themePresets.find((p) => p.id === settings.preset);
    if (preset) {
      Object.entries(preset.colors).forEach(([key, value]) => {
        if (value) {
          root.style.setProperty(`--${key}`, value);
        }
      });
    }

    // 应用自定义颜色
    Object.entries(settings.customColors).forEach(([key, value]) => {
      if (value) {
        root.style.setProperty(`--${key}`, value);
      }
    });

    // 应用字体大小
    const fontSizes = {
      sm: '14px',
      base: '16px',
      lg: '18px',
    };
    root.style.setProperty('--font-size-base', fontSizes[settings.fontSize]);
    root.style.fontSize = fontSizes[settings.fontSize];

    // 应用圆角
    const radiusValues = {
      none: '0',
      sm: '0.25rem',
      md: '0.5rem',
      lg: '0.75rem',
      full: '9999px',
    };
    root.style.setProperty('--radius', radiusValues[settings.radius]);

    // 应用减弱动画偏好
    if (settings.reducedMotion) {
      root.classList.add('reduce-motion');
    } else {
      root.classList.remove('reduce-motion');
    }
  }, [settings, resolvedMode]);

  // 操作方法
  const setMode = useCallback((mode: ThemeMode) => {
    setSettings((prev) => ({ ...prev, mode }));
  }, []);

  const toggleMode = useCallback(() => {
    setSettings((prev) => ({
      ...prev,
      mode: prev.mode === 'dark' ? 'light' : prev.mode === 'light' ? 'system' : 'dark',
    }));
  }, []);

  const setPreset = useCallback((presetId: string) => {
    const preset = themePresets.find((p) => p.id === presetId);
    if (preset) {
      setSettings((prev) => ({
        ...prev,
        preset: presetId,
        mode: preset.mode,
        customColors: {},
      }));
    }
  }, []);

  const setCustomColor = useCallback((key: keyof ThemeColors, value: string) => {
    setSettings((prev) => ({
      ...prev,
      customColors: { ...prev.customColors, [key]: value },
    }));
  }, []);

  const setFontSize = useCallback((fontSize: ThemeSettings['fontSize']) => {
    setSettings((prev) => ({ ...prev, fontSize }));
  }, []);

  const setRadius = useCallback((radius: ThemeSettings['radius']) => {
    setSettings((prev) => ({ ...prev, radius }));
  }, []);

  const setReducedMotion = useCallback((reducedMotion: boolean) => {
    setSettings((prev) => ({ ...prev, reducedMotion }));
  }, []);

  const resetToDefaults = useCallback(() => {
    setSettings(defaultSettings);
  }, []);

  const value = useMemo<EnhancedThemeContextValue>(
    () => ({
      mode: settings.mode,
      resolvedMode,
      preset: settings.preset,
      settings,
      setMode,
      toggleMode,
      setPreset,
      setCustomColor,
      setFontSize,
      setRadius,
      setReducedMotion,
      resetToDefaults,
      presets: themePresets,
    }),
    [settings, resolvedMode, setMode, toggleMode, setPreset, setCustomColor, setFontSize, setRadius, setReducedMotion, resetToDefaults]
  );

  return (
    <EnhancedThemeContext.Provider value={value}>
      {children}
    </EnhancedThemeContext.Provider>
  );
}

export function useEnhancedTheme() {
  const context = useContext(EnhancedThemeContext);
  if (!context) {
    // Return a safe read-only fallback instead of crashing the app.
    // This can happen when service worker serves stale chunks or during
    // ErrorBoundary rendering before providers mount.
    return _ENHANCED_FALLBACK;
  }
  return context;
}

// Minimal no-op fallback so components using useEnhancedTheme don't crash
const _noop = () => {};
const _ENHANCED_FALLBACK: EnhancedThemeContextValue = {
  mode: 'dark',
  resolvedMode: 'dark',
  preset: 'default-dark',
  settings: defaultSettings,
  setMode: _noop as EnhancedThemeContextValue['setMode'],
  toggleMode: _noop,
  setPreset: _noop as EnhancedThemeContextValue['setPreset'],
  setCustomColor: _noop as EnhancedThemeContextValue['setCustomColor'],
  setFontSize: _noop as EnhancedThemeContextValue['setFontSize'],
  setRadius: _noop as EnhancedThemeContextValue['setRadius'],
  setReducedMotion: _noop as EnhancedThemeContextValue['setReducedMotion'],
  resetToDefaults: _noop,
  presets: [],
};

export { themePresets };
export default EnhancedThemeProvider;

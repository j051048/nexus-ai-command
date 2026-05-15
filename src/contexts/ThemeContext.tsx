/* eslint-disable react-refresh/only-export-components */
import { useMemo, useCallback, ReactNode } from 'react';
import { useEnhancedTheme } from './EnhancedThemeContext';

type Theme = 'dark' | 'light';

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

// Safe fallback when ThemeProvider is missing (e.g. stale service worker cache,
// chunk mismatch, or ErrorBoundary fallback rendering).  Theme is non-critical —
// crashing the entire app over it is worse than falling back to dark mode.
const _FALLBACK: ThemeContextType = {
  theme: 'dark',
  toggleTheme: () => {},
  setTheme: () => {},
};

export function useTheme() {
  const { resolvedMode, toggleMode, setMode } = useEnhancedTheme();
  const setTheme = useCallback((theme: Theme) => setMode(theme), [setMode]);
  return useMemo<ThemeContextType>(() => ({
    theme: resolvedMode,
    toggleTheme: toggleMode,
    setTheme,
  }), [resolvedMode, toggleMode, setTheme]) ?? _FALLBACK;
}

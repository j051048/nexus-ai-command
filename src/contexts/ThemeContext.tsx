/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useMemo, useCallback, ReactNode } from 'react';
import { useEnhancedTheme } from './EnhancedThemeContext';

type Theme = 'dark' | 'light';

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { resolvedMode, toggleMode, setMode } = useEnhancedTheme();

  const setTheme = useCallback((theme: Theme) => setMode(theme), [setMode]);

  const value = useMemo<ThemeContextType>(() => ({
    theme: resolvedMode,
    toggleTheme: toggleMode,
    setTheme,
  }), [resolvedMode, toggleMode, setTheme]);

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
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
  const context = useContext(ThemeContext);
  return context ?? _FALLBACK;
}

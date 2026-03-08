import React from 'react';
import { useTheme } from '@/contexts/ThemeContext';
import { Sun, Moon } from 'lucide-react';
import { cn } from '@/lib/utils';

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      data-compact
      onClick={toggleTheme}
      title={isDark ? '切换到日间模式' : '切换到夜间模式'}
      className={cn(
        "relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0",
        isDark ? "bg-slate-700" : "bg-sky-200"
      )}
      aria-label="Toggle theme"
    >
      <div
        className={cn(
          "absolute top-0.5 w-5 h-5 rounded-full shadow-sm transition-all duration-300",
          "flex items-center justify-center bg-white",
          isDark ? "left-0.5" : "left-[22px]"
        )}
      >
        {isDark ? (
          <Moon className="w-3 h-3 text-slate-600" />
        ) : (
          <Sun className="w-3 h-3 text-amber-500" />
        )}
      </div>
    </button>
  );
}

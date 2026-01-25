import React from 'react';
import { useTheme } from '@/contexts/ThemeContext';
import { Sun, Moon } from 'lucide-react';
import { cn } from '@/lib/utils';

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={cn(
        "relative w-14 h-7 rounded-full p-1 transition-all duration-300",
        theme === 'dark' 
          ? "bg-secondary" 
          : "bg-primary/20"
      )}
      aria-label="Toggle theme"
    >
      <div
        className={cn(
          "absolute top-1 w-5 h-5 rounded-full transition-all duration-300 flex items-center justify-center",
          theme === 'dark'
            ? "left-1 bg-primary"
            : "left-8 bg-primary"
        )}
      >
        {theme === 'dark' ? (
          <Moon className="w-3 h-3 text-primary-foreground" />
        ) : (
          <Sun className="w-3 h-3 text-primary-foreground" />
        )}
      </div>
    </button>
  );
}

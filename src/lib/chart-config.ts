/**
 * 统一的图表配置
 */

export const chartConfig = {
  colors: {
    primary: ['#3b82f6', '#8b5cf6', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444'],
    gradient: ['#6366f1', '#a78bfa', '#ddd6fe'],
    success: '#22c55e',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#3b82f6',
  },

  tooltip: {
    contentStyle: {
      background: 'hsl(var(--card))',
      border: '1px solid hsl(var(--border))',
      borderRadius: 8,
      fontSize: 12,
      padding: '8px 12px',
    },
    labelStyle: {
      color: 'hsl(var(--foreground))',
      fontWeight: 600,
    },
  },

  animation: {
    duration: 800,
    easing: 'ease-out' as const,
  },

  grid: {
    stroke: 'hsl(var(--border))',
    strokeDasharray: '3 3',
  },
};

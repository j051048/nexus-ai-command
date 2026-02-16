/**
 * 图表颜色工具：使用 CSS 变量确保跟随主题切换
 * 在 recharts 中使用: fill={chartColors.primary} 或 stroke={chartColors.primary}
 */

function getCSSVar(name: string): string {
  if (typeof window === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function getChartColor(name: string): string {
  const val = getCSSVar(`--${name}`);
  return val ? `hsl(${val})` : '';
}

// 预定义的图表调色板（使用时会实时读取 CSS 变量）
export const CHART_COLORS = [
  'hsl(var(--primary))',
  'hsl(var(--primary) / 0.7)',
  'hsl(var(--primary) / 0.5)',
  'hsl(var(--primary) / 0.3)',
  'hsl(var(--accent, 142 69% 50%))',
  'hsl(var(--accent, 142 69% 50%) / 0.7)',
];

// 语义化颜色
export const chartColors = {
  primary: 'hsl(var(--primary))',
  primaryLight: 'hsl(var(--primary) / 0.7)',
  primaryMuted: 'hsl(var(--primary) / 0.4)',
  accent: 'hsl(var(--accent, 142 69% 50%))',
  success: '#22c55e',  // 保留语义色：成功
  warning: '#f59e0b',  // 保留语义色：警告
  danger: '#ef4444',   // 保留语义色：危险
  info: '#3b82f6',     // 保留语义色：信息
};

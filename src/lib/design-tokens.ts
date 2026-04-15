/**
 * 设计系统 - 设计令牌
 * 统一的颜色、间距、阴影等视觉规范
 */

// 状态颜色
export const statusColors = {
  pending: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  in_progress: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  failed: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
} as const;

// 语义化颜色
export const semanticColors = {
  success: 'text-green-600 dark:text-green-400',
  warning: 'text-amber-600 dark:text-amber-400',
  danger: 'text-red-600 dark:text-red-400',
  info: 'text-blue-600 dark:text-blue-400',
} as const;

// 图标颜色（用于统计卡片等）
export const iconColors = {
  blue: 'text-blue-500',
  green: 'text-green-500',
  orange: 'text-orange-500',
  purple: 'text-purple-500',
  red: 'text-red-500',
  cyan: 'text-cyan-500',
} as const;

// 背景颜色（用于图标容器）
export const iconBackgrounds = {
  blue: 'bg-blue-500/10',
  green: 'bg-green-500/10',
  orange: 'bg-orange-500/10',
  purple: 'bg-purple-500/10',
  red: 'bg-red-500/10',
  cyan: 'bg-cyan-500/10',
} as const;

// 间距系统（基于 4px）
export const spacing = {
  xs: 'gap-2',   // 8px
  sm: 'gap-4',   // 16px
  md: 'gap-6',   // 24px
  lg: 'gap-8',   // 32px
  xl: 'gap-12',  // 48px
} as const;

// 卡片内边距
export const cardPadding = {
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
} as const;

// 字体层级 (对齐 tailwind.config.ts 自定义 fontSize token)
export const typography = {
  h1: 'text-heading-lg',
  h2: 'text-heading',
  h3: 'text-heading-sm',
  h4: 'text-body-lg font-medium',
  body: 'text-body',
  small: 'text-body-sm',
  xs: 'text-caption text-muted-foreground',
} as const;

// 阴影层级
export const shadows = {
  sm: 'shadow-sm',
  md: 'shadow-md',
  lg: 'shadow-lg',
  xl: 'shadow-xl',
} as const;

// 圆角
export const radius = {
  sm: 'rounded-sm',
  md: 'rounded-md',
  lg: 'rounded-lg',
  full: 'rounded-full',
} as const;

// 过渡动画
export const transitions = {
  fast: 'transition-all duration-150 ease-in-out',
  normal: 'transition-all duration-200 ease-in-out',
  slow: 'transition-all duration-300 ease-in-out',
} as const;

/**
 * 设计系统 - 设计令牌
 * 统一的颜色、间距、阴影等视觉规范
 */

// 状态颜色
export const statusColors = {
  pending: 'border border-amber-500/25 bg-amber-500/8 text-amber-700 dark:text-amber-300',
  in_progress: 'border border-primary/25 bg-primary/8 text-primary',
  completed: 'border border-emerald-500/25 bg-emerald-500/8 text-emerald-700 dark:text-emerald-300',
  failed: 'border border-destructive/25 bg-destructive/8 text-destructive',
  cancelled: 'border border-border bg-muted/60 text-muted-foreground',
} as const;

// 语义化颜色
export const semanticColors = {
  success: 'text-emerald-700 dark:text-emerald-300',
  warning: 'text-amber-700 dark:text-amber-300',
  danger: 'text-destructive',
  info: 'text-primary',
} as const;

// 图标颜色（用于统计卡片等）
export const iconColors = {
  blue: 'text-primary',
  green: 'text-emerald-700 dark:text-emerald-300',
  orange: 'text-amber-700 dark:text-amber-300',
  purple: 'text-primary',
  red: 'text-destructive',
  cyan: 'text-primary',
} as const;

// 背景颜色（用于图标容器）
export const iconBackgrounds = {
  blue: 'border border-primary/20 bg-primary/8',
  green: 'border border-emerald-500/20 bg-emerald-500/8',
  orange: 'border border-amber-500/20 bg-amber-500/8',
  purple: 'border border-primary/20 bg-primary/8',
  red: 'border border-destructive/20 bg-destructive/8',
  cyan: 'border border-primary/20 bg-primary/8',
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
  md: 'shadow-[var(--shadow-card)]',
  lg: 'shadow-[var(--shadow-elevated)]',
  xl: 'shadow-[var(--shadow-elevated)]',
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

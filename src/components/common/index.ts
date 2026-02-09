/**
 * Common Components Index
 * 导出所有公共组件
 */

// Empty State Components
export {
  EmptyState,
  NoSearchResults,
  NoDataYet,
  LoadingError,
  type EmptyStateType,
} from './EmptyState';

// Command Palette
export { CommandPalette } from './CommandPalette';

// AI Copilot
export { default as AICopilotInsight } from './AICopilotInsight';

// Notification Center
export { default as NotificationCenter } from './NotificationCenter';

// Animated Components
export {
  FadeInView,
  StaggerList,
  AnimatedNumber,
  TypewriterText,
  SkeletonTransition,
  AnimatedProgress,
  PulseDot,
  Spinner,
  AnimatedGradient,
  HoverCardAnimated,
  ShakeWrapper,
} from './AnimatedComponents';

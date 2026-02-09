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
export { EnhancedNotificationCenter } from './EnhancedNotificationCenter';

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

// Multi-Step Form
export {
  MultiStepForm,
  StepContent,
  FormField,
  useMultiStepForm,
  type StepConfig,
  type MultiStepFormContextValue,
} from './MultiStepForm';

// Data Export
export {
  DataExport,
  QuickExport,
  type ExportFormat,
  type ExportColumn,
  type ExportConfig,
} from './DataExport';

// Micro Interactions
export {
  RippleButton,
  PressButton,
  SuccessButton,
  CopyButton,
  ToggleButton,
  ValidatedInput,
  ShakeInput,
  BounceBadge,
  SkeletonShimmer,
} from './MicroInteractions';

// Accessibility Components
export {
  SkipLink,
  VisuallyHidden,
  FocusableContainer,
  AccessibleList,
  LiveRegion,
  ProgressAnnouncer,
  KeyboardShortcut,
  FocusRing,
  AccessibleIconButton,
  ReducedMotionWrapper,
} from './AccessibilityComponents';

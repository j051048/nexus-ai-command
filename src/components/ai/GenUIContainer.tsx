import React, { lazy, Suspense } from 'react';
import { lazyWithRetry } from '@/lib/lazyPreload';
import { Skeleton } from '@/components/ui/skeleton';
import { GenUIToolbar } from './genui/GenUIToolbar';

// Registry of components available for Generative UI
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const GEN_UI_COMPONENTS: Record<string, React.ComponentType<any>> = {
  // Business components
  BadgePanel: lazyWithRetry(() => import('../dashboard/employee/BadgePanel').then(m => ({ default: m.BadgePanel }))),
  ApprovalCenter: lazyWithRetry(() => import('../approval/ApprovalCenter').then(m => ({ default: m.ApprovalCenter }))),
  RewardsWallet: lazyWithRetry(() => import('../rewards/RewardsWallet').then(m => ({ default: m.RewardsWallet }))),
  KanbanBoard: lazyWithRetry(() => import('../sales/sections/KanbanBoard').then(m => ({ default: m.KanbanBoard }))),
  PriorityLeads: lazyWithRetry(() => import('../sales/sections/PriorityLeads').then(m => ({ default: m.PriorityLeads }))),
  // Data visualization components
  DataChart: lazyWithRetry(() => import('./genui/DataChart')),
  DataTable: lazyWithRetry(() => import('./genui/DataTable')),
  StatCards: lazyWithRetry(() => import('./genui/StatCards')),
  // Interactive components
  TodoList: lazyWithRetry(() => import('./genui/TodoList')),
  Timeline: lazyWithRetry(() => import('./genui/Timeline')),
  // P1-7: Extended GenUI components
  ProgressTracker: lazyWithRetry(() => import('./genui/ProgressTracker')),
  MetricComparison: lazyWithRetry(() => import('./genui/MetricComparison')),
  AlertList: lazyWithRetry(() => import('./genui/AlertList')),
  FormBuilder: lazyWithRetry(() => import('./genui/FormBuilder')),
  UserProfileCard: lazyWithRetry(() => import('./genui/UserProfileCard')),
  // P3: Extended GenUI components (10 new)
  ApprovalFlow: lazyWithRetry(() => import('./genui/ApprovalFlow')),
  OrgChart: lazyWithRetry(() => import('./genui/OrgChart')),
  ComparisonTable: lazyWithRetry(() => import('./genui/ComparisonTable')),
  StatusTimeline: lazyWithRetry(() => import('./genui/StatusTimeline')),
  PieChart: lazyWithRetry(() => import('./genui/PieChart')),
  FunnelChart: lazyWithRetry(() => import('./genui/FunnelChart')),
  CalendarView: lazyWithRetry(() => import('./genui/CalendarView')),
  QuoteCard: lazyWithRetry(() => import('./genui/QuoteCard')),
  FileList: lazyWithRetry(() => import('./genui/FileList')),
  KanbanMini: lazyWithRetry(() => import('./genui/KanbanMini')),
};

interface GenUIContainerProps {
  componentName: string;
  props: Record<string, unknown>;
}

export const GenUIContainer = React.memo(function GenUIContainer({ componentName, props }: GenUIContainerProps) {
  const Component = GEN_UI_COMPONENTS[componentName];

  if (!Component) {
    console.warn(`Generative UI: Component "${componentName}" not found in registry.`);
    return null;
  }

  return (
    <div className="my-4 w-full overflow-hidden rounded-xl border border-border bg-card shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-500">
      <Suspense fallback={<GenUISkeleton />}>
        <GenUIToolbar componentName={componentName} props={props}>
          <Component {...props} />
        </GenUIToolbar>
      </Suspense>
    </div>
  );
});

function GenUISkeleton() {
  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-4 w-16" />
      </div>
      <div className="flex gap-4">
        <Skeleton className="h-24 w-24 rounded-xl" />
        <Skeleton className="h-24 w-24 rounded-xl" />
        <Skeleton className="h-24 w-24 rounded-xl" />
      </div>
    </div>
  );
}

import React, { lazy, Suspense } from 'react';
import { Skeleton } from '@/components/ui/skeleton';

// Registry of components available for Generative UI
// Registry of components available for Generative UI
const GEN_UI_COMPONENTS: Record<string, React.ComponentType<Record<string, any>>> = {
  BadgePanel: lazy(() => import('../dashboard/employee/BadgePanel').then(m => ({ default: m.BadgePanel }))),
  ApprovalCenter: lazy(() => import('../approval/ApprovalCenter').then(m => ({ default: m.ApprovalCenter }))),
  RewardsWallet: lazy(() => import('../rewards/RewardsWallet').then(m => ({ default: m.RewardsWallet }))), 
  KanbanBoard: lazy(() => import('../sales/sections/KanbanBoard').then(m => ({ default: m.KanbanBoard }))),
  PriorityLeads: lazy(() => import('../sales/sections/PriorityLeads').then(m => ({ default: m.PriorityLeads }))),
};

interface GenUIContainerProps {
  componentName: string;
  props: Record<string, unknown>;
}

export function GenUIContainer({ componentName, props }: GenUIContainerProps) {
  const Component = GEN_UI_COMPONENTS[componentName];

  if (!Component) {
    console.warn(`Generative UI: Component "${componentName}" not found in registry.`);
    return null;
  }

  return (
    <div className="my-4 w-full overflow-hidden rounded-xl border border-border bg-card shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-500">
      <Suspense fallback={<GenUISkeleton />}>
        <Component {...props} />
      </Suspense>
    </div>
  );
}

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

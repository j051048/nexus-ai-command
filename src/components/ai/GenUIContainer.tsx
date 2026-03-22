import React, { Suspense } from 'react';
import { lazyWithRetry } from '@/lib/lazyPreload';
import { Skeleton } from '@/components/ui/skeleton';
import { GenUIToolbar } from './genui/GenUIToolbar';
import { AlertTriangle, ExternalLink, RotateCcw } from 'lucide-react';
import { CRUD_FALLBACK_ROUTES } from './genui/GenUIToolbar';

// Registry of components available for Generative UI
// GenUI components use reloadOnFailure=false to prevent page reload on chunk failures;
// errors are caught by GenUIErrorBoundary instead.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const GEN_UI_COMPONENTS: Record<string, React.ComponentType<any>> = {
  // Business components
  BadgePanel: lazyWithRetry(() => import('../dashboard/employee/BadgePanel').then(m => ({ default: m.BadgePanel })), 2, false),
  ApprovalCenter: lazyWithRetry(() => import('../approval/ApprovalCenter').then(m => ({ default: m.ApprovalCenter })), 2, false),
  RewardsWallet: lazyWithRetry(() => import('../rewards/RewardsWallet').then(m => ({ default: m.RewardsWallet })), 2, false),
  KanbanBoard: lazyWithRetry(() => import('../sales/sections/KanbanBoard').then(m => ({ default: m.KanbanBoard })), 2, false),
  PriorityLeads: lazyWithRetry(() => import('../sales/sections/PriorityLeads').then(m => ({ default: m.PriorityLeads })), 2, false),
  // Data visualization components
  DataChart: lazyWithRetry(() => import('./genui/DataChart'), 2, false),
  DataTable: lazyWithRetry(() => import('./genui/DataTable'), 2, false),
  StatCards: lazyWithRetry(() => import('./genui/StatCards'), 2, false),
  Dashboard: lazyWithRetry(() => import('./genui/Dashboard'), 2, false),
  // Interactive components
  TodoList: lazyWithRetry(() => import('./genui/TodoList'), 2, false),
  Timeline: lazyWithRetry(() => import('./genui/Timeline'), 2, false),
  // P1-7: Extended GenUI components
  ProgressTracker: lazyWithRetry(() => import('./genui/ProgressTracker'), 2, false),
  MetricComparison: lazyWithRetry(() => import('./genui/MetricComparison'), 2, false),
  AlertList: lazyWithRetry(() => import('./genui/AlertList'), 2, false),
  FormBuilder: lazyWithRetry(() => import('./genui/FormBuilder'), 2, false),
  UserProfileCard: lazyWithRetry(() => import('./genui/UserProfileCard'), 2, false),
  // P3: Extended GenUI components (10 new)
  ApprovalFlow: lazyWithRetry(() => import('./genui/ApprovalFlow'), 2, false),
  OrgChart: lazyWithRetry(() => import('./genui/OrgChart'), 2, false),
  ComparisonTable: lazyWithRetry(() => import('./genui/ComparisonTable'), 2, false),
  StatusTimeline: lazyWithRetry(() => import('./genui/StatusTimeline'), 2, false),
  PieChart: lazyWithRetry(() => import('./genui/PieChart'), 2, false),
  FunnelChart: lazyWithRetry(() => import('./genui/FunnelChart'), 2, false),
  CalendarView: lazyWithRetry(() => import('./genui/CalendarView'), 2, false),
  QuoteCard: lazyWithRetry(() => import('./genui/QuoteCard'), 2, false),
  FileList: lazyWithRetry(() => import('./genui/FileList'), 2, false),
  KanbanMini: lazyWithRetry(() => import('./genui/KanbanMini'), 2, false),
  // P4: Report & Communication components
  ReportCard: lazyWithRetry(() => import('./genui/ReportCard'), 2, false),
  DailyReport: lazyWithRetry(() => import('./genui/ReportCard'), 2, false),
  EmailDraft: lazyWithRetry(() => import('./genui/EmailDraft'), 2, false),
  // P5: Business Logic & Data Visualization
  ContractPreview: lazyWithRetry(() => import('./genui/ContractPreview'), 2, false),
  InvoiceCard: lazyWithRetry(() => import('./genui/InvoiceCard'), 2, false),
  GeoChart: lazyWithRetry(() => import('./genui/GeoChart'), 2, false),
  GanttChart: lazyWithRetry(() => import('./genui/GanttChart'), 2, false),
  DataGrid: lazyWithRetry(() => import('./genui/DataGrid'), 2, false),
  Heatmap: lazyWithRetry(() => import('./genui/Heatmap'), 2, false),
};

interface GenUIContainerProps {
  componentName: string;
  props: Record<string, unknown>;
  onSendMessage?: (prompt: string) => void;
}

// ErrorBoundary that catches render errors locally within GenUI components,
// preventing them from bubbling up to the global ErrorBoundary and crashing the page.
interface GenUIErrorBoundaryProps {
  componentName: string;
  children: React.ReactNode;
}

interface GenUIErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class GenUIErrorBoundary extends React.Component<GenUIErrorBoundaryProps, GenUIErrorBoundaryState> {
  constructor(props: GenUIErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): GenUIErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error(
      `[GenUI] Component "${this.props.componentName}" render failed:`,
      error,
      errorInfo.componentStack
    );
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      const fallbackRoute = CRUD_FALLBACK_ROUTES[this.props.componentName];
      return (
        <div className="p-4 flex flex-col items-center gap-3 text-center">
          <div className="rounded-full bg-amber-500/10 p-2.5">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">
              组件渲染失败
            </p>
            <p className="text-xs text-muted-foreground">
              「{this.props.componentName}」加载出错，请重试
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={this.handleRetry}
              className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors"
            >
              <RotateCcw className="h-3 w-3" />
              重新加载
            </button>
            {fallbackRoute && (
              <button
                onClick={() => window.open(fallbackRoute, '_blank')}
                className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors"
              >
                <ExternalLink className="h-3 w-3" />
                前往手动页面
              </button>
            )}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export const GenUIContainer = React.memo(function GenUIContainer({ componentName, props, onSendMessage }: GenUIContainerProps) {
  const Component = GEN_UI_COMPONENTS[componentName];

  if (!Component) {
    console.warn(`Generative UI: Component "${componentName}" not found in registry.`);
    return null;
  }

  // Inject onSendMessage for interactive components (Dashboard, DataChart)
  const enhancedProps = onSendMessage ? { ...props, onSendMessage } : props;

  return (
    <div className="my-4 w-full overflow-hidden rounded-xl border border-border bg-card shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-500">
      <GenUIErrorBoundary componentName={componentName}>
        <Suspense fallback={<GenUISkeleton />}>
          <GenUIToolbar componentName={componentName} props={props}>
            <Component {...enhancedProps} />
          </GenUIToolbar>
        </Suspense>
      </GenUIErrorBoundary>
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

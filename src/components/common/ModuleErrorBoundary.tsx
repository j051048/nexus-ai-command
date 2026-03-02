import React from 'react';
import * as Sentry from '@sentry/react';

interface ModuleErrorBoundaryProps {
  children: React.ReactNode;
  /** Module name for logging, e.g. "AI聊天", "仪表盘" */
  moduleName: string;
  /** Optional custom fallback. Defaults to a compact inline error card. */
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Module-level ErrorBoundary for graceful degradation.
 * When a child component crashes, only this module shows an error card
 * instead of taking down the entire application.
 */
export class ModuleErrorBoundary extends React.Component<ModuleErrorBoundaryProps, State> {
  constructor(props: ModuleErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error(`[${this.props.moduleName}] Module error:`, error, errorInfo);

    // Auto-reload on chunk load failure (new deployment invalidated old chunks)
    if (this.isChunkLoadError(error)) {
      const reloadKey = 'chunk-reload';
      const lastReload = sessionStorage.getItem(reloadKey);
      const now = Date.now();
      if (!lastReload || now - Number(lastReload) > 10000) {
        sessionStorage.setItem(reloadKey, String(now));
        window.location.reload();
        return;
      }
    }

    if (import.meta.env.PROD) {
      Sentry.captureException(error, {
        tags: { module: this.props.moduleName },
        extra: { componentStack: errorInfo.componentStack },
      });
    }
  }

  private isChunkLoadError(error: Error): boolean {
    const msg = error.message || '';
    return msg.includes('Failed to fetch dynamically imported module') ||
           msg.includes('Loading chunk') ||
           msg.includes('Loading CSS chunk');
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-6 text-center">
          <div className="text-sm font-medium text-destructive">
            {this.props.moduleName}模块加载异常
          </div>
          <p className="text-xs text-muted-foreground max-w-sm">
            {this.state.error?.message || '发生了未知错误'}
          </p>
          <button
            onClick={this.handleRetry}
            className="mt-1 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

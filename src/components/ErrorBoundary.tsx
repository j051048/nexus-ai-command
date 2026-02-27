import React from "react";
import { AlertCircle, Home, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
  showDetails: boolean;
}

/**
 * Global ErrorBoundary - catches any unhandled React render errors
 * and displays a friendly Chinese error page instead of a white screen.
 *
 * Must be a class component (React requirement for error boundaries).
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("[GlobalErrorBoundary] Uncaught error:", error);
    console.error("[GlobalErrorBoundary] Component stack:", errorInfo.componentStack);
    this.setState({ errorInfo });
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoHome = () => {
    window.location.href = "/";
  };

  private toggleDetails = () => {
    this.setState((prev) => ({ showDetails: !prev.showDetails }));
  };

  render() {
    if (this.state.hasError) {
      const isDev = import.meta.env.DEV;

      return (
        <div className="min-h-screen bg-background flex items-center justify-center p-6">
          <div className="max-w-lg w-full space-y-6 text-center">
            {/* Icon */}
            <div className="flex justify-center">
              <div className="rounded-full bg-destructive/10 p-4">
                <AlertCircle className="h-12 w-12 text-destructive" />
              </div>
            </div>

            {/* Title */}
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold text-foreground">
                页面出现异常
              </h1>
              <p className="text-muted-foreground">
                很抱歉，页面发生了意外错误。请尝试刷新页面或返回首页。
              </p>
            </div>

            {/* Action buttons */}
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={this.handleReload}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <RefreshCw className="h-4 w-4" />
                重新加载
              </button>
              <button
                onClick={this.handleGoHome}
                className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-4 py-2.5 text-sm font-medium text-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                <Home className="h-4 w-4" />
                返回首页
              </button>
            </div>

            {/* Development mode: collapsible error details */}
            {isDev && this.state.error && (
              <div className="mt-4 text-left">
                <button
                  onClick={this.toggleDetails}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mx-auto"
                >
                  {this.state.showDetails ? (
                    <ChevronUp className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                  {this.state.showDetails ? "收起错误详情" : "展开错误详情"}
                </button>

                {this.state.showDetails && (
                  <div className="mt-3 rounded-lg border border-destructive/20 bg-destructive/5 p-4 space-y-3 overflow-auto max-h-80">
                    <div>
                      <p className="text-xs font-medium text-destructive mb-1">
                        错误信息
                      </p>
                      <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-words">
                        {this.state.error.message}
                      </pre>
                    </div>
                    {this.state.error.stack && (
                      <div>
                        <p className="text-xs font-medium text-destructive mb-1">
                          堆栈跟踪
                        </p>
                        <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-words font-mono">
                          {this.state.error.stack}
                        </pre>
                      </div>
                    )}
                    {this.state.errorInfo?.componentStack && (
                      <div>
                        <p className="text-xs font-medium text-destructive mb-1">
                          组件堆栈
                        </p>
                        <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-words font-mono">
                          {this.state.errorInfo.componentStack}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

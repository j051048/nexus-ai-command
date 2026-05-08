import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/components/auth/AuthContext";
import { GlobalCommandBar } from "@/components/layout/GlobalCommandBar";
import { EnhancedThemeProvider } from "@/contexts/EnhancedThemeContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { I18nProvider } from "@/lib/i18n";
import { PageContextProvider } from "@/hooks/usePageContext";
import { LoginPage } from "@/components/auth/LoginPage";
import { ResetPasswordPage } from "@/components/auth/ResetPasswordPage";
import React, { Suspense } from "react";
import * as Sentry from "@sentry/react";
import { toast } from "sonner";
import { ErrorBoundary } from "@/components/ErrorBoundary";
// P1 #22: Lazy load ProductTour (~50KB react-joyride) — only needed for new users
const ProductTour = React.lazy(() =>
  import("@/components/common/ProductTour").then(m => ({ default: m.ProductTour }))
);
import { DashboardLayout, NotFound, AdminPanel } from "@/routes/lazyImports";
import { coreRoutes } from "@/routes/coreRoutes";
import { businessRoutes } from "@/routes/businessRoutes";
import { adminRoutes } from "@/routes/adminRoutes";
import { vmdRoutes } from "@/routes/vmdRoutes";

// P0 Fix: Initialize Sentry for production error tracking
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
if (SENTRY_DSN && import.meta.env.PROD) {
  Sentry.init({
    dsn: SENTRY_DSN,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.2,
    environment: import.meta.env.MODE,
  });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
    mutations: {
      onError: (error) => {
        toast.error(error instanceof Error ? error.message : '操作失败，请重试');
      },
    },
  },
});

function LoadingFallback() {
  return (
    <div className="min-h-screen bg-background">
      <div className="flex h-screen">
        <aside className="hidden md:flex w-72 shrink-0 flex-col border-r bg-sidebar p-4">
          <div className="h-10 w-36 rounded-lg bg-sidebar-accent animate-pulse" />
          <div className="mt-8 space-y-3">
            {Array.from({ length: 8 }).map((_, index) => (
              <div
                key={index}
                className="h-9 rounded-xl bg-sidebar-accent/70 animate-pulse"
                style={{ width: `${86 - (index % 3) * 9}%` }}
              />
            ))}
          </div>
          <div className="mt-auto h-14 rounded-2xl bg-sidebar-accent/70 animate-pulse" />
        </aside>
        <main className="flex-1 overflow-hidden p-4 md:p-8">
          <div className="mb-8 flex items-center justify-between gap-4">
            <div className="space-y-3">
              <div className="h-8 w-48 rounded-lg bg-muted animate-pulse" />
              <div className="h-4 w-72 max-w-[70vw] rounded bg-muted/70 animate-pulse" />
            </div>
            <div className="hidden sm:block h-10 w-28 rounded-xl bg-muted animate-pulse" />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="h-28 rounded-lg border bg-card p-4">
                <div className="h-4 w-20 rounded bg-muted animate-pulse" />
                <div className="mt-6 h-7 w-24 rounded bg-muted/80 animate-pulse" />
              </div>
            ))}
          </div>
          <div className="mt-6 h-[46vh] rounded-lg border bg-card p-4">
            <div className="h-5 w-40 rounded bg-muted animate-pulse" />
            <div className="mt-6 space-y-3">
              {Array.from({ length: 7 }).map((_, index) => (
                <div key={index} className="h-10 rounded bg-muted/70 animate-pulse" />
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingFallback />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AdminRoute({ children, allowedRoles = ['boss'] }: { children: React.ReactNode; allowedRoles?: string[] }) {
  const { user, role, loading } = useAuth();
  if (loading) return <LoadingFallback />;
  if (!user) return <Navigate to="/login" replace />;
  if (!role || !allowedRoles.includes(role)) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingFallback />;
  if (user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function SuperAdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, isSuperAdmin } = useAuth();
  if (loading) return <LoadingFallback />;
  if (!user) return <Navigate to="/login" replace />;
  if (!isSuperAdmin) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

const App = () => (
  <ErrorBoundary>
  <QueryClientProvider client={queryClient}>
    <I18nProvider>
    <EnhancedThemeProvider>
    <ThemeProvider>
    <TooltipProvider>
      <Sonner position="top-right" expand={false} richColors closeButton />
      <BrowserRouter>
        <AuthProvider>
          <PageContextProvider>
          <Suspense fallback={null}><ProductTour /></Suspense>
          <GlobalCommandBar />
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/admin" element={<SuperAdminRoute><AdminPanel /></SuperAdminRoute>} />

              <Route path="/" element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
                {coreRoutes(AdminRoute)}
                {businessRoutes()}
                {adminRoutes(AdminRoute)}
                {vmdRoutes()}
                <Route path="*" element={<NotFound />} />
              </Route>

              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
          </PageContextProvider>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
    </ThemeProvider>
    </EnhancedThemeProvider>
    </I18nProvider>
  </QueryClientProvider>
  </ErrorBoundary>
);

export default App;

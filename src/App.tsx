import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/components/auth/AuthContext";
import { GlobalCommandBar } from "@/components/layout/GlobalCommandBar";
import { EnhancedThemeProvider } from "@/contexts/EnhancedThemeContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { I18nProvider } from "@/lib/i18n";
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
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full" />
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

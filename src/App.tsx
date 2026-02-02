import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/components/auth/AuthContext";
import { LoginPage } from "@/components/auth/LoginPage";
import { ResetPasswordPage } from "@/components/auth/ResetPasswordPage";
import React, { Suspense, lazy } from "react";

// Lazy load pages for better performance
const DashboardLayout = lazy(() => import("./pages/Index"));
const NotFound = lazy(() => import("./pages/NotFound"));

// Lazy load feature pages
const EmployeeDashboard = lazy(() => import("@/components/dashboard/EmployeeDashboard").then(m => ({ default: m.EmployeeDashboard })));
const BossDashboard = lazy(() => import("@/components/dashboard/BossDashboard").then(m => ({ default: m.BossDashboard })));
const ProjectManagement = lazy(() => import("@/pages/ProjectManagement").then(m => ({ default: m.ProjectManagement })));
const ProjectDetail = lazy(() => import("@/components/projects/ProjectDetail").then(m => ({ default: m.ProjectDetail })));
const SalesPipeline = lazy(() => import("@/components/sales/SalesPipeline").then(m => ({ default: m.SalesPipeline })));
const ApprovalCenter = lazy(() => import("@/components/approval/ApprovalCenter").then(m => ({ default: m.ApprovalCenter })));
const ExceptionsPage = lazy(() => import("@/pages/ExceptionsPage")); // Default export likely
const RewardsWallet = lazy(() => import("@/components/rewards/RewardsWallet").then(m => ({ default: m.RewardsWallet })));
const SalesTargetManager = lazy(() => import("@/components/targets/SalesTargetManager").then(m => ({ default: m.SalesTargetManager })));
const TenderAnalysisPage = lazy(() => import("@/pages/TenderAnalysisPage").then(m => ({ default: m.TenderAnalysisPage })));
const BattlecardLibrary = lazy(() => import("@/pages/BattlecardLibrary").then(m => ({ default: m.BattlecardLibrary })));
const TargetDashboard = lazy(() => import("@/pages/TargetDashboard").then(m => ({ default: m.TargetDashboard })));
const DocumentsPage = lazy(() => import("@/components/documents/DocumentsPage").then(m => ({ default: m.DocumentsPage })));
const AISettingsPanel = lazy(() => import("@/components/settings/AISettingsPanel").then(m => ({ default: m.AISettingsPanel })));
const EmployeeManagement = lazy(() => import("@/components/admin/EmployeeManagement").then(m => ({ default: m.EmployeeManagement })));

const queryClient = new QueryClient();

function LoadingFallback() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full" />
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <LoadingFallback />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <LoadingFallback />;
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

              {/* Main App Routes */}
              <Route path="/" element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<EmployeeDashboard />} />
                <Route path="boss-dashboard" element={<BossDashboard />} />
                <Route path="projects" element={<ProjectManagement />} />
                <Route path="projects/:id" element={<ProjectDetail />} />
                <Route path="sales" element={<SalesPipeline />} />
                <Route path="approval" element={<ApprovalCenter />} />
                <Route path="exceptions" element={<ExceptionsPage />} />
                <Route path="rewards" element={<RewardsWallet />} />
                <Route path="targets" element={<SalesTargetManager />} />
                <Route path="target-dashboard" element={<TargetDashboard />} />
                <Route path="tender-analysis" element={<TenderAnalysisPage />} />
                <Route path="battlecards" element={<BattlecardLibrary />} />
                <Route path="documents" element={<DocumentsPage />} />
                <Route path="knowledge" element={<DocumentsPage />} />
                <Route path="settings" element={<AISettingsPanel />} />
                <Route path="employees" element={<EmployeeManagement />} />
              </Route>

              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;

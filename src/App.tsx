import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/components/auth/AuthContext";
import { GlobalCommandBar } from "@/components/layout/GlobalCommandBar";
import { EnhancedThemeProvider } from "@/contexts/EnhancedThemeContext";
import { I18nProvider } from "@/lib/i18n";
import { LoginPage } from "@/components/auth/LoginPage";
import { ResetPasswordPage } from "@/components/auth/ResetPasswordPage";
import React, { Suspense, lazy } from "react";
import * as Sentry from "@sentry/react";
import { toast } from "sonner";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";

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

class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode; resetKey?: string },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode; fallback?: React.ReactNode; resetKey?: string }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidUpdate(prevProps: { resetKey?: string }) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: null });
    }
  }
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Page load error:', error, errorInfo);
    // P0 Fix: Report to Sentry in production
    if (SENTRY_DSN && import.meta.env.PROD) {
      Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } });
    }
  }
  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4">
          <p className="text-destructive text-lg">页面加载失败</p>
          <button className="px-4 py-2 bg-primary text-primary-foreground rounded" onClick={() => window.location.reload()}>
            刷新页面
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

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
const DepartmentManagement = lazy(() => import("@/pages/DepartmentManagement"));
const AnimationShowcase = lazy(() => import("@/pages/AnimationShowcase"));

// 可视化流程设计器
const WorkflowList = lazy(() => import("@/pages/WorkflowList"));
const WorkflowDesigner = lazy(() => import("@/pages/WorkflowDesigner"));

// AI-First 企业管理页面
const OACenter = lazy(() => import("@/pages/OACenter"));
const HRCenter = lazy(() => import("@/pages/HRCenter"));
const FinanceCenter = lazy(() => import("@/pages/FinanceCenter"));
const ProfileCenter = lazy(() => import("@/pages/ProfileCenter"));
const DataImportPage = lazy(() => import("@/pages/DataImportPage"));
const FormDesigner = lazy(() => import("@/pages/FormDesigner"));

// P2: 可定制仪表板 + 审计面板
const CustomDashboard = lazy(() => import("@/pages/CustomDashboard"));
const AuditPanel = lazy(() => import("@/pages/AuditPanel"));

// P3: 模板市场 + 消息中心 + 报表 + 支付 + CRM
const WorkflowTemplates = lazy(() => import("@/pages/WorkflowTemplates"));
const NotificationCenter = lazy(() => import("@/pages/NotificationCenter"));
const ReportsPage = lazy(() => import("@/pages/ReportsPage"));
const PaymentPage = lazy(() => import("@/pages/PaymentPage"));
const CRMPage = lazy(() => import("@/pages/CRMPage"));

// P4: 插件市场 + 培训中心 + 合同管理 + 超管 + API密钥
const PluginMarketplace = lazy(() => import("@/pages/PluginMarketplace"));
const TrainingCenter = lazy(() => import("@/pages/TrainingCenter"));
const ContractManagement = lazy(() => import("@/pages/ContractManagement"));
const SuperAdminDashboard = lazy(() => import("@/pages/SuperAdminDashboard"));
const APIKeysPage = lazy(() => import("@/pages/APIKeysPage"));

// VMD (Virtual Marketing Department) pages
const VMDCenter = lazy(() => import("@/pages/VMDCenter"));
const VMDTaskCenter = lazy(() => import("@/pages/VMDTaskCenter"));
const VMDAgentConfig = lazy(() => import("@/pages/VMDAgentConfig"));
const LLMModelManagement = lazy(() => import("@/pages/LLMModelManagement"));
const VMDClueManagement = lazy(() => import("@/pages/VMDClueManagement"));
const VMDDashboard = lazy(() => import("@/pages/VMDDashboard"));
const VMDCompliancePage = lazy(() => import("@/pages/VMDCompliancePage"));
const AgentDebugPanel = lazy(() => import("@/pages/AgentDebugPanel"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
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

  if (loading) {
    return <LoadingFallback />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// P0 Security Fix: Role-based route guard for admin pages
function AdminRoute({ children, allowedRoles = ['boss'] }: { children: React.ReactNode; allowedRoles?: string[] }) {
  const { user, role, loading } = useAuth();

  if (loading) {
    return <LoadingFallback />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!role || !allowedRoles.includes(role)) {
    return <Navigate to="/dashboard" replace />;
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

function RouteErrorBoundary({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <I18nProvider>
    <EnhancedThemeProvider>
    <TooltipProvider>
      <Sonner position="top-right" expand={false} richColors closeButton />
      <Toaster />
      <BrowserRouter>
        <AuthProvider>
          <GlobalCommandBar />
          <RouteErrorBoundary><Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

              {/* Main App Routes */}
              <Route path="/" element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<ModuleErrorBoundary moduleName="仪表盘"><EmployeeDashboard /></ModuleErrorBoundary>} />
                <Route path="boss-dashboard" element={<ModuleErrorBoundary moduleName="管理驾驶舱"><BossDashboard /></ModuleErrorBoundary>} />
                <Route path="projects" element={<ModuleErrorBoundary moduleName="项目管理"><ProjectManagement /></ModuleErrorBoundary>} />
                <Route path="projects/:id" element={<ModuleErrorBoundary moduleName="项目详情"><ProjectDetail /></ModuleErrorBoundary>} />
                <Route path="sales" element={<ModuleErrorBoundary moduleName="销售管道"><SalesPipeline /></ModuleErrorBoundary>} />
                <Route path="approval" element={<ModuleErrorBoundary moduleName="审批中心"><ApprovalCenter /></ModuleErrorBoundary>} />
                <Route path="exceptions" element={<ModuleErrorBoundary moduleName="异常管理"><ExceptionsPage /></ModuleErrorBoundary>} />
                <Route path="rewards" element={<ModuleErrorBoundary moduleName="奖励钱包"><RewardsWallet /></ModuleErrorBoundary>} />
                <Route path="targets" element={<ModuleErrorBoundary moduleName="销售目标"><SalesTargetManager /></ModuleErrorBoundary>} />
                <Route path="target-dashboard" element={<ModuleErrorBoundary moduleName="目标仪表盘"><TargetDashboard /></ModuleErrorBoundary>} />
                <Route path="tender-analysis" element={<ModuleErrorBoundary moduleName="标书分析"><TenderAnalysisPage /></ModuleErrorBoundary>} />
                <Route path="battlecards" element={<ModuleErrorBoundary moduleName="竞品卡片"><BattlecardLibrary /></ModuleErrorBoundary>} />
                <Route path="documents" element={<ModuleErrorBoundary moduleName="知识库"><DocumentsPage /></ModuleErrorBoundary>} />
                <Route path="knowledge" element={<ModuleErrorBoundary moduleName="知识库"><DocumentsPage /></ModuleErrorBoundary>} />
                <Route path="settings" element={<ModuleErrorBoundary moduleName="AI设置"><AISettingsPanel /></ModuleErrorBoundary>} />
                <Route path="employees" element={<AdminRoute allowedRoles={['boss', 'manager']}><ModuleErrorBoundary moduleName="员工管理"><EmployeeManagement /></ModuleErrorBoundary></AdminRoute>} />
                <Route path="departments" element={<ModuleErrorBoundary moduleName="部门管理"><DepartmentManagement /></ModuleErrorBoundary>} />

                {/* 可视化流程设计器 */}
                <Route path="workflows" element={<ModuleErrorBoundary moduleName="工作流"><WorkflowList /></ModuleErrorBoundary>} />
                <Route path="workflows/new" element={<ModuleErrorBoundary moduleName="工作流设计"><WorkflowDesigner /></ModuleErrorBoundary>} />
                <Route path="workflows/:id" element={<ModuleErrorBoundary moduleName="工作流设计"><WorkflowDesigner /></ModuleErrorBoundary>} />

                {/* AI-First 企业管理页面 */}
                <Route path="oa" element={<ModuleErrorBoundary moduleName="OA办公"><OACenter /></ModuleErrorBoundary>} />
                <Route path="hr" element={<ModuleErrorBoundary moduleName="人力资源"><HRCenter /></ModuleErrorBoundary>} />
                <Route path="finance" element={<ModuleErrorBoundary moduleName="财务中心"><FinanceCenter /></ModuleErrorBoundary>} />
                <Route path="profile" element={<ModuleErrorBoundary moduleName="个人中心"><ProfileCenter /></ModuleErrorBoundary>} />
                <Route path="import" element={<ModuleErrorBoundary moduleName="数据导入"><DataImportPage /></ModuleErrorBoundary>} />

                {/* 自定义表单设计器 */}
                <Route path="form-designer" element={<ModuleErrorBoundary moduleName="表单设计"><FormDesigner /></ModuleErrorBoundary>} />
                <Route path="form-designer/:id" element={<ModuleErrorBoundary moduleName="表单设计"><FormDesigner /></ModuleErrorBoundary>} />

                {/* P2: 可定制仪表板 + 审计 */}
                <Route path="custom-dashboard" element={<ModuleErrorBoundary moduleName="自定义仪表盘"><CustomDashboard /></ModuleErrorBoundary>} />
                <Route path="audit" element={<ModuleErrorBoundary moduleName="审计面板"><AuditPanel /></ModuleErrorBoundary>} />

                {/* P3: 模板市场 + 消息中心 + 报表 + 支付 + CRM */}
                <Route path="workflow-templates" element={<ModuleErrorBoundary moduleName="工作流模板"><WorkflowTemplates /></ModuleErrorBoundary>} />
                <Route path="notification-center" element={<ModuleErrorBoundary moduleName="消息中心"><NotificationCenter /></ModuleErrorBoundary>} />
                <Route path="reports" element={<ModuleErrorBoundary moduleName="报表"><ReportsPage /></ModuleErrorBoundary>} />
                <Route path="payments" element={<ModuleErrorBoundary moduleName="支付"><PaymentPage /></ModuleErrorBoundary>} />
                <Route path="crm" element={<ModuleErrorBoundary moduleName="CRM"><CRMPage /></ModuleErrorBoundary>} />

                {/* P4: 插件 + 培训 + 合同 + 超管 + API密钥 */}
                <Route path="plugins" element={<ModuleErrorBoundary moduleName="插件市场"><PluginMarketplace /></ModuleErrorBoundary>} />
                <Route path="training" element={<ModuleErrorBoundary moduleName="培训中心"><TrainingCenter /></ModuleErrorBoundary>} />
                <Route path="contracts" element={<ModuleErrorBoundary moduleName="合同管理"><ContractManagement /></ModuleErrorBoundary>} />
                <Route path="super-admin" element={<AdminRoute><ModuleErrorBoundary moduleName="超级管理"><SuperAdminDashboard /></ModuleErrorBoundary></AdminRoute>} />
                <Route path="api-keys" element={<AdminRoute><ModuleErrorBoundary moduleName="API密钥"><APIKeysPage /></ModuleErrorBoundary></AdminRoute>} />

                {/* VMD (Virtual Marketing Department) */}
                <Route path="vmd" element={<ModuleErrorBoundary moduleName="VMD"><VMDCenter /></ModuleErrorBoundary>} />
                <Route path="vmd/tasks" element={<ModuleErrorBoundary moduleName="VMD任务"><VMDTaskCenter /></ModuleErrorBoundary>} />
                <Route path="vmd/agents" element={<ModuleErrorBoundary moduleName="VMD代理"><VMDAgentConfig /></ModuleErrorBoundary>} />
                <Route path="vmd/clues" element={<ModuleErrorBoundary moduleName="VMD线索"><VMDClueManagement /></ModuleErrorBoundary>} />
                <Route path="vmd/compliance" element={<ModuleErrorBoundary moduleName="VMD合规"><VMDCompliancePage /></ModuleErrorBoundary>} />
                <Route path="vmd/dashboard" element={<ModuleErrorBoundary moduleName="VMD仪表盘"><VMDDashboard /></ModuleErrorBoundary>} />
                <Route path="llm/models" element={<AdminRoute><ModuleErrorBoundary moduleName="LLM模型"><LLMModelManagement /></ModuleErrorBoundary></AdminRoute>} />

                {/* Developer Tools */}
                <Route path="dev/animations" element={<AnimationShowcase />} />
                <Route path="agent-debug" element={<AdminRoute><ModuleErrorBoundary moduleName="调试面板"><AgentDebugPanel /></ModuleErrorBoundary></AdminRoute>} />

                {/* 404 for authenticated users */}
                <Route path="*" element={<NotFound />} />
              </Route>

              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense></RouteErrorBoundary>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
    </EnhancedThemeProvider>
    </I18nProvider>
  </QueryClientProvider>
);

export default App;

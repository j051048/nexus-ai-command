import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/components/auth/AuthContext";
import { GlobalCommandBar } from "@/components/layout/GlobalCommandBar";
import { EnhancedThemeProvider } from "@/contexts/EnhancedThemeContext";
import { I18nProvider } from "@/lib/i18n";
import { LoginPage } from "@/components/auth/LoginPage";
import { ResetPasswordPage } from "@/components/auth/ResetPasswordPage";
import React, { Suspense, lazy } from "react";
import { lazyWithRetry } from "@/lib/lazyPreload";
import * as Sentry from "@sentry/react";
import { toast } from "sonner";
import { ModuleErrorBoundary } from "@/components/common/ModuleErrorBoundary";
import { ErrorBoundary } from "@/components/ErrorBoundary";

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

// Lazy load pages with retry logic for deployment chunk failures
const DashboardLayout = lazyWithRetry(() => import("./pages/Index"));
const NotFound = lazyWithRetry(() => import("./pages/NotFound"));

// Lazy load feature pages
const EmployeeDashboard = lazyWithRetry(() => import("@/components/dashboard/EmployeeDashboard").then(m => ({ default: m.EmployeeDashboard })));
const BossDashboard = lazyWithRetry(() => import("@/components/dashboard/BossDashboard").then(m => ({ default: m.BossDashboard })));
const ProjectManagement = lazyWithRetry(() => import("@/pages/ProjectManagement").then(m => ({ default: m.ProjectManagement })));
const ProjectDetail = lazyWithRetry(() => import("@/components/projects/ProjectDetail").then(m => ({ default: m.ProjectDetail })));
const SalesPipeline = lazyWithRetry(() => import("@/components/sales/SalesPipeline").then(m => ({ default: m.SalesPipeline })));
const ApprovalCenter = lazyWithRetry(() => import("@/components/approval/ApprovalCenter").then(m => ({ default: m.ApprovalCenter })));
const ExceptionsPage = lazyWithRetry(() => import("@/pages/ExceptionsPage"));
const RewardsWallet = lazyWithRetry(() => import("@/components/rewards/RewardsWallet").then(m => ({ default: m.RewardsWallet })));
const SalesTargetManager = lazyWithRetry(() => import("@/components/targets/SalesTargetManager").then(m => ({ default: m.SalesTargetManager })));
const TenderAnalysisPage = lazyWithRetry(() => import("@/pages/TenderAnalysisPage").then(m => ({ default: m.TenderAnalysisPage })));
const BattlecardLibrary = lazyWithRetry(() => import("@/pages/BattlecardLibrary").then(m => ({ default: m.BattlecardLibrary })));
const TargetDashboard = lazyWithRetry(() => import("@/pages/TargetDashboard").then(m => ({ default: m.TargetDashboard })));
const DocumentsPage = lazyWithRetry(() => import("@/components/documents/DocumentsPage").then(m => ({ default: m.DocumentsPage })));
const AISettingsPanel = lazyWithRetry(() => import("@/components/settings/AISettingsPanel").then(m => ({ default: m.AISettingsPanel })));
const EmployeeManagement = lazyWithRetry(() => import("@/components/admin/EmployeeManagement").then(m => ({ default: m.EmployeeManagement })));
const DepartmentManagement = lazyWithRetry(() => import("@/pages/DepartmentManagement"));
const AnimationShowcase = lazyWithRetry(() => import("@/pages/AnimationShowcase"));

// 可视化流程设计器
const WorkflowList = lazyWithRetry(() => import("@/pages/WorkflowList"));
const WorkflowDesigner = lazyWithRetry(() => import("@/pages/WorkflowDesigner"));

// AI-First 企业管理页面
const OACenter = lazyWithRetry(() => import("@/pages/OACenter"));
const HRCenter = lazyWithRetry(() => import("@/pages/HRCenter"));
const FinanceCenter = lazyWithRetry(() => import("@/pages/FinanceCenter"));
const ProfileCenter = lazyWithRetry(() => import("@/pages/ProfileCenter"));
const DataImportPage = lazyWithRetry(() => import("@/pages/DataImportPage"));
const FormDesigner = lazyWithRetry(() => import("@/pages/FormDesigner"));

// P2: 可定制仪表板 + 审计面板
const CustomDashboard = lazyWithRetry(() => import("@/pages/CustomDashboard"));
const AuditPanel = lazyWithRetry(() => import("@/pages/AuditPanel"));

// P3: 模板市场 + 消息中心 + 报表 + 支付 + CRM
const WorkflowTemplates = lazyWithRetry(() => import("@/pages/WorkflowTemplates"));
const NotificationCenter = lazyWithRetry(() => import("@/pages/NotificationCenter"));
const ReportsPage = lazyWithRetry(() => import("@/pages/ReportsPage"));
const PaymentPage = lazyWithRetry(() => import("@/pages/PaymentPage"));
const CRMPage = lazyWithRetry(() => import("@/pages/CRMPage"));

// P4: 插件市场 + 培训中心 + 合同管理 + 超管 + API密钥
const PluginMarketplace = lazyWithRetry(() => import("@/pages/PluginMarketplace"));
const TrainingCenter = lazyWithRetry(() => import("@/pages/TrainingCenter"));
const ContractManagement = lazyWithRetry(() => import("@/pages/ContractManagement"));
const SuperAdminDashboard = lazyWithRetry(() => import("@/pages/SuperAdminDashboard"));
const APIKeysPage = lazyWithRetry(() => import("@/pages/APIKeysPage"));

// VMD (Virtual Marketing Department) pages
const VMDCenter = lazyWithRetry(() => import("@/pages/VMDCenter"));
const VMDTaskCenter = lazyWithRetry(() => import("@/pages/VMDTaskCenter"));
const VMDAgentConfig = lazyWithRetry(() => import("@/pages/VMDAgentConfig"));
const LLMModelManagement = lazyWithRetry(() => import("@/pages/LLMModelManagement"));
const VMDClueManagement = lazyWithRetry(() => import("@/pages/VMDClueManagement"));
const VMDDashboard = lazyWithRetry(() => import("@/pages/VMDDashboard"));
const VMDCompliancePage = lazyWithRetry(() => import("@/pages/VMDCompliancePage"));
const AgentDebugPanel = lazyWithRetry(() => import("@/pages/AgentDebugPanel"));
const LLMCostDashboard = lazyWithRetry(() => import("@/pages/LLMCostDashboard"));
const CompanySettingsPage = lazyWithRetry(() => import("@/pages/CompanySettingsPage"));
const AdminPanel = lazyWithRetry(() => import("@/pages/AdminPanel"));
const OrgChartPage = lazyWithRetry(() => import("@/pages/OrgChartPage"));

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

// Super Admin route guard — checks isSuperAdmin flag from AuthContext
function SuperAdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, isSuperAdmin } = useAuth();

  if (loading) {
    return <LoadingFallback />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!isSuperAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

const App = () => (
  <ErrorBoundary>
  <QueryClientProvider client={queryClient}>
    <I18nProvider>
    <EnhancedThemeProvider>
    <TooltipProvider>
      <Sonner position="top-right" expand={false} richColors closeButton />
      <Toaster />
      <BrowserRouter>
        <AuthProvider>
          <GlobalCommandBar />
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />

              {/* Super Admin Panel — standalone layout, no sidebar */}
              <Route path="/admin" element={<SuperAdminRoute><AdminPanel /></SuperAdminRoute>} />

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
                <Route path="llm/costs" element={<AdminRoute><ModuleErrorBoundary moduleName="LLM成本"><LLMCostDashboard /></ModuleErrorBoundary></AdminRoute>} />
                <Route path="company-settings" element={<AdminRoute><ModuleErrorBoundary moduleName="企业设置"><CompanySettingsPage /></ModuleErrorBoundary></AdminRoute>} />
                <Route path="org-chart" element={<AdminRoute><ModuleErrorBoundary moduleName="组织架构"><OrgChartPage /></ModuleErrorBoundary></AdminRoute>} />

                {/* Developer Tools */}
                <Route path="dev/animations" element={<AnimationShowcase />} />
                <Route path="agent-debug" element={<AdminRoute><ModuleErrorBoundary moduleName="调试面板"><AgentDebugPanel /></ModuleErrorBoundary></AdminRoute>} />

                {/* 404 for authenticated users */}
                <Route path="*" element={<NotFound />} />
              </Route>

              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
    </EnhancedThemeProvider>
    </I18nProvider>
  </QueryClientProvider>
  </ErrorBoundary>
);

export default App;

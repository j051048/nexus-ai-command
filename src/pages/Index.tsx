import React, { useState } from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { UserProvider } from '@/contexts/UserContext';
import { useAuth } from '@/components/auth/AuthContext';
import { MainLayout } from '@/components/layout/MainLayout';
import { Loader2 } from 'lucide-react';
import { Navigate } from 'react-router-dom';

// Lazy load main sections
const EmployeeDashboard = React.lazy(() => import('@/components/dashboard/EmployeeDashboard').then(m => ({ default: m.EmployeeDashboard })));
const BossDashboard = React.lazy(() => import('@/components/dashboard/BossDashboard').then(m => ({ default: m.BossDashboard })));
const SalesPipeline = React.lazy(() => import('@/components/sales/SalesPipeline').then(m => ({ default: m.SalesPipeline })));
const ApprovalCenter = React.lazy(() => import('@/components/approval/ApprovalCenter').then(m => ({ default: m.ApprovalCenter })));
const RewardsWallet = React.lazy(() => import('@/components/rewards/RewardsWallet').then(m => ({ default: m.RewardsWallet })));
const SalesTargetManager = React.lazy(() => import('@/components/targets/SalesTargetManager').then(m => ({ default: m.SalesTargetManager })));
const EmployeeManagement = React.lazy(() => import('@/components/admin/EmployeeManagement').then(m => ({ default: m.EmployeeManagement })));
const AISettingsPanel = React.lazy(() => import('@/components/settings/AISettingsPanel').then(m => ({ default: m.AISettingsPanel })));
const ProjectDetail = React.lazy(() => import('@/components/projects/ProjectDetail').then(m => ({ default: m.ProjectDetail })));
const ExceptionsPage = React.lazy(() => import('./ExceptionsPage'));

const PageLoader = () => (
  <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
    <Loader2 className="w-10 h-10 animate-spin text-primary" />
    <p className="text-muted-foreground animate-pulse">正在加载模块...</p>
  </div>
);

function AppContent() {
  const { role } = useAuth();
  const [activeNav, setActiveNav] = useState(role === 'boss' ? 'boss-dashboard' : 'dashboard');
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  // Update nav when role changes
  React.useEffect(() => {
    setActiveNav(role === 'boss' ? 'boss-dashboard' : 'dashboard');
  }, [role]);

  const renderContent = () => {
    switch (activeNav) {
      case 'dashboard':
        return <EmployeeDashboard />;
      case 'boss-dashboard':
        return <BossDashboard />;
      case 'exceptions':
        return <ExceptionsPage />;
      case 'team-performance':
        return <BossDashboard />;
      case 'sales':
        return <SalesPipeline />;
      case 'approval':
        return <ApprovalCenter />;
      case 'rewards':
        return <RewardsWallet />;
      case 'targets':
        return <SalesTargetManager />;
      case 'employees':
        return <EmployeeManagement onProjectSelect={(id) => {
          setSelectedProjectId(id);
          setActiveNav('project-detail');
        }} />;
      case 'project-detail':
        return selectedProjectId ? (
          <ProjectDetail
            projectId={selectedProjectId}
            onBack={() => setActiveNav('employees')}
          />
        ) : <Navigate to="/" />;
      case 'knowledge':
        return (
          <div className="flex items-center justify-center h-96">
            <div className="text-center">
              <div className="text-6xl mb-4">📚</div>
              <h2 className="text-xl font-semibold text-foreground">知识库</h2>
              <p className="text-muted-foreground mt-2">产品参数、竞品对比、技术文档</p>
            </div>
          </div>
        );
      case 'settings':
        return <AISettingsPanel />;
      default:
        return <EmployeeDashboard />;
    }
  };

  return (
    <UserProvider>
      <MainLayout activeNav={activeNav} onNavChange={setActiveNav}>
        <React.Suspense fallback={<PageLoader />}>
          {renderContent()}
        </React.Suspense>
      </MainLayout>
    </UserProvider>
  );
}

const Index = () => {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
};

export default Index;

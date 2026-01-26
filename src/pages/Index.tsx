import React, { useState } from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { UserProvider } from '@/contexts/UserContext';
import { useAuth } from '@/components/auth/AuthContext';
import { MainLayout } from '@/components/layout/MainLayout';
import { Loader2 } from 'lucide-react';
import { Navigate } from 'react-router-dom';

// Lazy load main sections
// Lazy load main sections
import { EmployeeDashboard } from '@/components/dashboard/EmployeeDashboard';
import { BossDashboard } from '@/components/dashboard/BossDashboard';
import { routes } from '@/config/routes';

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
        return <routes.ExceptionsPage />;
      case 'team-performance':
        return <BossDashboard />;
      case 'sales':
        return <routes.SalesPipeline />;
      case 'approval':
        return <routes.ApprovalCenter />;
      case 'rewards':
        return <routes.RewardsWallet />;
      case 'targets':
        return <routes.SalesTargetManager />;
      case 'employees':
        return <routes.EmployeeManagement onProjectSelect={(id) => {
          setSelectedProjectId(id);
          setActiveNav('project-detail');
        }} />;
      case 'project-detail':
        return selectedProjectId ? (
          <routes.ProjectDetail
            projectId={selectedProjectId}
            onBack={() => setActiveNav('employees')}
          />
        ) : <Navigate to="/" />;
      case 'documents':
        return <routes.DocumentsPage />;
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
        return <routes.AISettingsPanel />;
      default:
        return <EmployeeDashboard />;
    }
  };

  return (
    <UserProvider>
      <MainLayout activeNav={activeNav} onNavChange={setActiveNav}>
        {renderContent()}
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

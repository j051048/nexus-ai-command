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
      case 'projects':
        return <routes.ProjectManagement onProjectSelect={(id) => {
          setSelectedProjectId(id);
          setActiveNav('project-detail');
        }} />;
      case 'tender-analysis':
        return <routes.TenderAnalysisPage />;
      case 'battlecards':
        return <routes.BattlecardLibrary />;
      case 'target-dashboard':
        return <routes.TargetDashboard />;
      case 'project-detail':
        return selectedProjectId ? (
          <routes.ProjectDetail
            projectId={selectedProjectId}
            onBack={() => setActiveNav(role === 'boss' ? 'employees' : 'projects')}
          />
        ) : <Navigate to="/" />;
      case 'documents':
      case 'knowledge':
        return <routes.DocumentsPage onNavigate={(nav) => setActiveNav(nav)} />;
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

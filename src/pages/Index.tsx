import React, { useState } from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { UserProvider } from '@/contexts/UserContext';
import { useAuth } from '@/components/auth/AuthContext';
import { MainLayout } from '@/components/layout/MainLayout';
import { EmployeeDashboard } from '@/components/dashboard/EmployeeDashboard';
import { BossDashboard } from '@/components/dashboard/BossDashboard';
import { SalesPipeline } from '@/components/sales/SalesPipeline';
import { ApprovalCenter } from '@/components/approval/ApprovalCenter';
import { RewardsWallet } from '@/components/rewards/RewardsWallet';
import { SalesTargetManager } from '@/components/targets/SalesTargetManager';
import { EmployeeManagement } from '@/components/admin/EmployeeManagement';

function AppContent() {
  const { role } = useAuth();
  const [activeNav, setActiveNav] = useState(role === 'boss' ? 'boss-dashboard' : 'dashboard');

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
        return <BossDashboard />;
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
        return <EmployeeManagement />;
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
        return (
          <div className="flex items-center justify-center h-96">
            <div className="text-center">
              <div className="text-6xl mb-4">⚙️</div>
              <h2 className="text-xl font-semibold text-foreground">系统设置</h2>
              <p className="text-muted-foreground mt-2">配置AI规则、激励参数、权限管理</p>
            </div>
          </div>
        );
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

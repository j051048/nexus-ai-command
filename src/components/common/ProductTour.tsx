import { useState, useEffect } from 'react';
import { Joyride, Step, STATUS } from 'react-joyride';
import { useLocation } from 'react-router-dom';
import { useAuth } from '@/components/auth/AuthContext';

const tourSteps: Step[] = [
  {
    target: 'body',
    content: '欢迎使用 Nexus AI Command！让我带您快速了解核心功能。',
    placement: 'center',
  },
  {
    target: '[data-tour="chat"]',
    content: '这是 AI 对话框，您可以用自然语言完成所有操作，比如"创建一个销售线索"。',
  },
  {
    target: '[data-tour="sidebar"]',
    content: '左侧导航栏包含所有功能模块：CRM、审批、项目、文档等。',
  },
  {
    target: '[data-tour="dashboard"]',
    content: '仪表盘展示您的关键数据和待办事项。',
  },
  {
    target: '[data-tour="profile"]',
    content: '点击这里可以管理个人设置、AI 配置和退出登录。',
  },
];

export function ProductTour() {
  const [run, setRun] = useState(false);
  const { user, loading } = useAuth();
  const { pathname } = useLocation();

  useEffect(() => {
    // The tour belongs to the authenticated workspace. Keeping it off public
    // and platform-admin routes prevents first-visit overlays on auth screens.
    const isTest = import.meta.env.VITE_SKIP_TOUR === 'true';
    const hasSeenTour = localStorage.getItem('hasSeenTour') === 'true';
    const isWorkspaceRoute = !['/login', '/reset-password', '/admin'].some(
      route => pathname === route || pathname.startsWith(`${route}/`),
    );

    if (!loading && user && isWorkspaceRoute && !hasSeenTour && !isTest) {
      const timer = setTimeout(() => setRun(true), 1000);
      return () => clearTimeout(timer);
    }

    setRun(false);
  }, [loading, pathname, user]);

  // Use any with eslint-disable for the complex Joyride callback data type
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleJoyrideCallback = (data: any) => {
    const { status } = data;
    if (([STATUS.FINISHED, STATUS.SKIPPED] as string[]).includes(status)) {
      localStorage.setItem('hasSeenTour', 'true');
      setRun(false);
    }
  };

  return (
    <Joyride
      steps={tourSteps}
      run={run}
      continuous
      scrollToFirstStep={true}
      options={{
        showProgress: true,
        primaryColor: 'hsl(var(--primary))',
        zIndex: 10000,
        buttons: ['back', 'close', 'primary', 'skip'],
      }}
      locale={{
        back: '上一步',
        close: '关闭',
        last: '完成',
        next: '下一步',
        skip: '跳过',
      }}
      onEvent={handleJoyrideCallback}
    />
  );
}

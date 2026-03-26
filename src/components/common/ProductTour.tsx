import { useState, useEffect } from 'react';
import Joyride, { Step, CallBackProps, STATUS } from 'react-joyride';

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

  useEffect(() => {
    const hasSeenTour = localStorage.getItem('hasSeenTour');
    if (!hasSeenTour) {
      setTimeout(() => setRun(true), 1000);
    }
  }, []);

  const handleJoyrideCallback = (data: CallBackProps) => {
    const { status } = data;
    if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
      localStorage.setItem('hasSeenTour', 'true');
      setRun(false);
    }
  };

  return (
    <Joyride
      steps={tourSteps}
      run={run}
      continuous
      showProgress
      showSkipButton
      locale={{
        back: '上一步',
        close: '关闭',
        last: '完成',
        next: '下一步',
        skip: '跳过',
      }}
      styles={{
        options: {
          primaryColor: 'hsl(var(--primary))',
          zIndex: 10000,
        },
      }}
      callback={handleJoyrideCallback}
    />
  );
}

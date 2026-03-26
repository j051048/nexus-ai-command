import Joyride from 'react-joyride';

const steps = [
  { target: '.dashboard', content: '这是您的仪表板' },
  { target: '.create-btn', content: '点击这里创建新任务' }
];

export default function Onboarding() {
  return <Joyride steps={steps} continuous showProgress />;
}

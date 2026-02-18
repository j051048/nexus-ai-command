import { Target } from 'lucide-react';
import { FeatureComingSoon } from '@/components/common/FeatureComingSoon';

export function TargetDashboard() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Target className="w-8 h-8 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">个人目标看板</h1>
          <p className="text-muted-foreground">设定和追踪您的销售目标</p>
        </div>
      </div>
      <FeatureComingSoon
        title="个人目标看板"
        description="目标设定、进度追踪、AI 策略建议等功能正在建设中，敬请期待"
      />
    </div>
  );
}

export default TargetDashboard;

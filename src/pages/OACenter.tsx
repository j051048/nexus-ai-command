import { FeatureComingSoon } from '@/components/common/FeatureComingSoon';

export function OACenter() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">OA 办公中心</h1>
        <p className="text-muted-foreground">管理您的请假、会议和任务</p>
      </div>
      <FeatureComingSoon
        title="OA 办公中心"
        description="请假管理、会议预约、任务管理等功能正在建设中，敬请期待"
      />
    </div>
  );
}

export default OACenter;

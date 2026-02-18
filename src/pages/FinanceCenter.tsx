import { FeatureComingSoon } from '@/components/common/FeatureComingSoon';

export function FinanceCenter() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">财务中心</h1>
        <p className="text-muted-foreground">管理报销申请和查看预算</p>
      </div>
      <FeatureComingSoon
        title="财务中心"
        description="报销管理、预算概览等财务功能正在建设中，敬请期待"
      />
    </div>
  );
}

export default FinanceCenter;

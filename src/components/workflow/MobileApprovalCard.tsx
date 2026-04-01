/**
 * 移动端审批卡片组件
 * Phase 3: 移动端优化展示
 */
import React from 'react';
import { Badge } from '@/components/ui/badge';

interface MobileApprovalCardProps {
  request: {
    id: string;
    title: string;
    type: string;
    status: string;
    amount?: number;
    currentStep: string;
    currentApprover: string;
    stepIndex: number;
    totalSteps: number;
  };
  onViewDetails: (id: string) => void;
}

export function MobileApprovalCard({ request, onViewDetails }: MobileApprovalCardProps) {
  const statusColors = {
    pending: 'bg-orange-100 text-orange-700',
    approved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
    current: 'bg-blue-100 text-blue-700',
  };

  const typeLabels = {
    expense: '费用报销',
    leave: '请假申请',
    purchase: '采购申请',
    travel: '差旅申请',
  };

  return (
    <div className="mobile-approval-card bg-white rounded-lg shadow-sm p-4 mb-3">
      {/* 头部 */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Badge className={statusColors[request.status]}>
              {request.status === 'pending' ? '待审批' :
               request.status === 'approved' ? '已通过' :
               request.status === 'rejected' ? '已驳回' : '进行中'}
            </Badge>
          </div>
          <h3 className="font-medium text-base">{request.title}</h3>
        </div>
      </div>

      {/* 金额/类型 */}
      <div className="flex items-center gap-4 mb-3 text-sm">
        <div className="flex items-center gap-1">
          <span className="text-gray-500">类型:</span>
          <span>{typeLabels[request.type] || request.type}</span>
        </div>
        {request.amount && (
          <div className="flex items-center gap-1">
            <span className="text-gray-500">金额:</span>
            <span className="font-medium">¥{request.amount.toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* 当前进度 */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-gray-600">当前: {request.currentStep}</span>
          <span className="text-gray-500">{request.stepIndex}/{request.totalSteps}</span>
        </div>
        <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-300"
            style={{ width: `${(request.stepIndex / request.totalSteps) * 100}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">审批人: {request.currentApprover}</p>
      </div>

      {/* 操作按钮 */}
      <button
        className="w-full py-2 bg-blue-500 text-white rounded-lg active:bg-blue-600 transition-colors"
        onClick={() => onViewDetails(request.id)}
      >
        查看详情
      </button>
    </div>
  );
}
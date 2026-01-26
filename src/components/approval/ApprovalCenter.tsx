import React from 'react';
import { useAuth } from '@/components/auth/AuthContext';
import { useApprovalsRealtime } from '@/hooks/useApprovals';
import { useNotificationsRealtime } from '@/hooks/useNotifications';
import { NotificationBell } from './sections/NotificationBell';
import { EmployeeApprovalView } from './sections/EmployeeApprovalView';
import { BossApprovalView } from './sections/BossApprovalView';

export function ApprovalCenter() {
  const { role } = useAuth();
  const isBoss = role === 'boss';

  // Enable realtime subscriptions for the entire section
  useApprovalsRealtime();
  useNotificationsRealtime();

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-20 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* Header with Title and Global Actions */}
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h1 className="text-3xl font-extrabold text-foreground tracking-tight">智能审批中心</h1>
          <p className="text-muted-foreground mt-2 flex items-center gap-2">
            {isBoss ? (
              <>AI 引擎正在自动扫描常规申请，仅将异常推送至此处</>
            ) : (
              <>支持语音或自然输入，AI 秒级分类并处理</>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <NotificationBell />
        </div>
      </div>

      {/* Conditional View Rendering based on User Role */}
      <main>
        {isBoss ? <BossApprovalView /> : <EmployeeApprovalView />}
      </main>
    </div>
  );
}

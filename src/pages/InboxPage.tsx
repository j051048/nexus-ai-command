/**
 * InboxPage - 统一待办中心
 * 聚合：审批请求 + 异常待办 + 系统通知
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  FileCheck,
  AlertTriangle,
  Bell,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Filter,
} from 'lucide-react';
import { useApprovals } from '@/hooks/useApprovals';
import { useExceptions, type ExceptionAlert } from '@/hooks/useExceptions';
import {
  useNotificationCenter,
  useMarkRead,
  useMarkAllRead,
  type NotificationItem,
} from '@/hooks/useNotificationCenter';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

type TabKey = 'all' | 'approvals' | 'exceptions' | 'notifications';

interface TabDef {
  key: TabKey;
  label: string;
  icon: React.ElementType;
  count: number;
}

export default function InboxPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabKey>('all');

  // Data hooks
  const { pendingApprovals = [], updateStatus, isLoading: approvalsLoading } = useApprovals();
  const { data: exceptions = [], isLoading: exceptionsLoading } = useExceptions();
  const { data: notifications = [], isLoading: notificationsLoading } = useNotificationCenter({ limit: 50 });
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();

  const unreadNotifications = notifications.filter((n: NotificationItem) => !n.is_read);

  const tabs: TabDef[] = [
    { key: 'all', label: '全部', icon: Filter, count: pendingApprovals.length + exceptions.length + unreadNotifications.length },
    { key: 'approvals', label: '待审批', icon: FileCheck, count: pendingApprovals.length },
    { key: 'exceptions', label: '异常待办', icon: AlertTriangle, count: exceptions.length },
    { key: 'notifications', label: '通知', icon: Bell, count: unreadNotifications.length },
  ];

  const isLoading = approvalsLoading || exceptionsLoading || notificationsLoading;

  const handleApprove = async (id: string) => {
    try {
      await updateStatus.mutateAsync({ id, status: 'approved' });
      toast.success('审批已通过');
    } catch {
      toast.error('操作失败');
    }
  };

  const handleReject = async (id: string) => {
    try {
      await updateStatus.mutateAsync({ id, status: 'rejected' });
      toast.success('已拒绝');
    } catch {
      toast.error('操作失败');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllRead.mutateAsync();
      toast.success('已全部标为已读');
    } catch {
      toast.error('操作失败');
    }
  };

  const handleNotificationClick = async (notification: NotificationItem) => {
    if (!notification.is_read) {
      markRead.mutate([notification.id]);
    }
    if (notification.action_url) {
      navigate(notification.action_url);
    }
  };

  // Render sections
  const showApprovals = activeTab === 'all' || activeTab === 'approvals';
  const showExceptions = activeTab === 'all' || activeTab === 'exceptions';
  const showNotifications = activeTab === 'all' || activeTab === 'notifications';

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">待办中心</h1>
          <p className="text-sm text-muted-foreground mt-1">
            聚合所有待处理事项，一站式高效处理
          </p>
        </div>
        {unreadNotifications.length > 0 && (
          <Button variant="outline" size="sm" onClick={handleMarkAllRead}>
            全部已读
          </Button>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-2 border-b pb-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                activeTab === tab.key
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
              {tab.count > 0 && (
                <Badge variant="secondary" className="ml-1 h-5 min-w-[20px] px-1.5 text-[10px]">
                  {tab.count}
                </Badge>
              )}
            </button>
          );
        })}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full" />
        </div>
      )}

      {/* Approvals Section */}
      {showApprovals && pendingApprovals.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
            <FileCheck className="h-4 w-4" />
            待审批 ({pendingApprovals.length})
          </h2>
          <div className="space-y-2">
            {pendingApprovals.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {item.type === 'leave' ? '请假申请' : item.type === 'expense' ? '报销申请' : item.type} - {item.submitter_name || '未知用户'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {item.details ? (typeof item.details === 'string' ? item.details : JSON.stringify(item.details).slice(0, 80)) : ''}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {new Date(item.created_at).toLocaleString('zh-CN')}
                  </p>
                </div>
                <div className="flex items-center gap-2 ml-4 shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-destructive hover:text-destructive"
                    onClick={() => handleReject(item.id)}
                    disabled={updateStatus.isPending}
                  >
                    <XCircle className="h-3.5 w-3.5 mr-1" />
                    拒绝
                  </Button>
                  <Button
                    size="sm"
                    className="h-8"
                    onClick={() => handleApprove(item.id)}
                    disabled={updateStatus.isPending}
                  >
                    <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                    通过
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Exceptions Section */}
      {showExceptions && exceptions.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            异常待办 ({exceptions.length})
          </h2>
          <div className="space-y-2">
            {exceptions.map((item: ExceptionAlert) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors cursor-pointer"
                onClick={() => navigate('/exceptions')}
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <span
                    className={cn(
                      'w-2 h-2 rounded-full shrink-0',
                      item.severity === 'high' && 'bg-destructive',
                      item.severity === 'medium' && 'bg-warning',
                      item.severity === 'low' && 'bg-muted-foreground',
                    )}
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{item.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{item.description}</p>
                  </div>
                </div>
                <ExternalLink className="h-4 w-4 text-muted-foreground shrink-0 ml-2" />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Notifications Section */}
      {showNotifications && notifications.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
            <Bell className="h-4 w-4" />
            通知 ({unreadNotifications.length} 未读)
          </h2>
          <div className="space-y-2">
            {(activeTab === 'notifications' ? notifications : unreadNotifications.slice(0, 10)).map((item: NotificationItem) => (
              <div
                key={item.id}
                className={cn(
                  'flex items-start gap-3 p-4 rounded-lg border transition-colors cursor-pointer',
                  item.is_read
                    ? 'bg-card/50 opacity-70'
                    : 'bg-card hover:bg-accent/50',
                )}
                onClick={() => handleNotificationClick(item)}
              >
                <span
                  className={cn(
                    'mt-1 w-2 h-2 rounded-full shrink-0',
                    item.is_read ? 'bg-transparent' : 'bg-primary',
                  )}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.title}</p>
                  {item.content && (
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{item.content}</p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    {new Date(item.created_at).toLocaleString('zh-CN')}
                  </p>
                </div>
                {item.action_url && (
                  <ExternalLink className="h-4 w-4 text-muted-foreground shrink-0 mt-1" />
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Empty state */}
      {!isLoading &&
        pendingApprovals.length === 0 &&
        exceptions.length === 0 &&
        unreadNotifications.length === 0 && (
          <div className="text-center py-16">
            <CheckCircle2 className="h-12 w-12 text-success mx-auto mb-4 opacity-50" />
            <h3 className="text-lg font-medium">一切就绪</h3>
            <p className="text-sm text-muted-foreground mt-1">
              暂无待处理事项，可以专注于当前工作
            </p>
          </div>
        )}
    </div>
  );
}

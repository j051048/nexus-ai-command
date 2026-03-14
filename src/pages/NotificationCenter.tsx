import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import {
  Bell,
  BellOff,
  CheckCheck,
  Loader2,
  Info,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileCheck,
  Settings2,
  ExternalLink,
  Inbox,
  Mail,
  Smartphone,
  MessageSquare,
  Moon,
} from 'lucide-react';
import {
  useNotificationCenter,
  useUnreadCount,
  useMarkRead,
  useMarkAllRead,
  useNotificationPreferences,
  useUpdateNotificationPreferences,
} from '@/hooks/useNotificationCenter';
import { useNotificationsRealtime } from '@/hooks/useNotifications';
import type { NotificationItem } from '@/hooks/useNotificationCenter';

// ─── Constants ──────────────────────────────────────────────

type NotificationType = NotificationItem['type'];

const TYPE_ICONS: Record<NotificationType, React.ReactNode> = {
  info: <Info className="w-4 h-4 text-blue-500" />,
  success: <CheckCircle2 className="w-4 h-4 text-green-500" />,
  warning: <AlertTriangle className="w-4 h-4 text-yellow-500" />,
  error: <XCircle className="w-4 h-4 text-red-500" />,
  approval: <FileCheck className="w-4 h-4 text-purple-500" />,
  system: <Settings2 className="w-4 h-4 text-gray-500" />,
};

const TYPE_LABELS: Record<NotificationType, string> = {
  info: '信息',
  success: '成功',
  warning: '警告',
  error: '错误',
  approval: '审批',
  system: '系统',
};

const CATEGORY_LABELS: Record<string, string> = {
  approval: '审批通知',
  system: '系统通知',
  ai: 'AI 助手通知',
  report: '报表通知',
};

// ─── Helpers ────────────────────────────────────────────────

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;
  if (diffHour < 24) return `${diffHour} 小时前`;
  if (diffDay < 7) return `${diffDay} 天前`;
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

// ─── Component ──────────────────────────────────────────────

function NotificationCenter() {
  const navigate = useNavigate();
  const [filterType, setFilterType] = useState<string | undefined>(undefined);
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);

  // Realtime subscription — instantly refresh on new notifications
  useNotificationsRealtime();

  // Data hooks
  const { data: notifications = [], isLoading } = useNotificationCenter({
    unreadOnly: showUnreadOnly,
    type: filterType,
  });
  const { data: unreadCount = 0 } = useUnreadCount();
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();
  const { data: preferences } = useNotificationPreferences();
  const updatePreferences = useUpdateNotificationPreferences();

  // Handlers
  const handleMarkAllRead = async () => {
    try {
      await markAllRead.mutateAsync();
      toast.success('已全部标记为已读');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleNotificationClick = async (notification: NotificationItem) => {
    // Mark as read
    if (!notification.is_read) {
      markRead.mutate([notification.id]);
    }
    // Navigate if action_url
    if (notification.action_url) {
      if (notification.action_url.startsWith('http')) {
        window.open(notification.action_url, '_blank');
      } else {
        navigate(notification.action_url);
      }
    }
  };

  const handlePreferenceToggle = (key: string, value: boolean) => {
    updatePreferences.mutate({ [key]: value });
  };

  const handleCategoryToggle = (category: string, enabled: boolean) => {
    const currentCategories = preferences?.categories ?? {};
    updatePreferences.mutate({
      categories: { ...currentCategories, [category]: enabled },
    });
  };

  return (
    <div className="grid gap-3 md:gap-6 px-4 md:px-0 py-2 md:py-0">
      {/* Page Header — hidden on mobile (MobilePageHeader already shows title) */}
      <div className="hidden md:flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bell className="w-6 h-6" />
            消息中心
            {unreadCount > 0 && (
              <Badge variant="destructive" className="text-xs ml-1">
                {unreadCount > 99 ? '99+' : unreadCount}
              </Badge>
            )}
          </h1>
          <p className="text-muted-foreground mt-1">
            管理站内通知和消息偏好设置
          </p>
        </div>
        {unreadCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleMarkAllRead}
            disabled={markAllRead.isPending}
            className="gap-2"
          >
            {markAllRead.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <CheckCheck className="w-4 h-4" />
            )}
            全部已读
          </Button>
        )}
      </div>

      {/* Tabs: Notifications / Preferences */}
      <Tabs defaultValue="notifications">
        <TabsList>
          <TabsTrigger value="notifications" className="gap-1.5">
            <Bell className="w-4 h-4" />
            通知列表
          </TabsTrigger>
          <TabsTrigger value="preferences" className="gap-1.5">
            <Settings2 className="w-4 h-4" />
            偏好设置
          </TabsTrigger>
        </TabsList>

        {/* ─── Notifications Tab ──────────────────────────── */}
        <TabsContent value="notifications" className="grid gap-3 md:gap-4 mt-2 md:mt-4">
          {/* Mobile: mark-all-read button (desktop has it in page header) */}
          {unreadCount > 0 && (
            <div className="flex md:hidden justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={handleMarkAllRead}
                disabled={markAllRead.isPending}
                className="gap-1.5 h-8 text-xs"
              >
                {markAllRead.isPending ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <CheckCheck className="w-3 h-3" />
                )}
                全部已读
              </Button>
            </div>
          )}

          {/* Filters — horizontally scrollable on mobile */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 flex-nowrap md:flex-wrap" style={{ scrollbarWidth: 'none' }}>
            <Button
              variant={showUnreadOnly ? 'default' : 'outline'}
              size="sm"
              onClick={() => setShowUnreadOnly(!showUnreadOnly)}
              className="gap-1.5 shrink-0"
            >
              {showUnreadOnly ? <BellOff className="w-3 h-3" /> : <Bell className="w-3 h-3" />}
              {showUnreadOnly ? '仅未读' : '全部'}
            </Button>
            <Separator orientation="vertical" className="h-6 shrink-0" />
            <Button
              variant={!filterType ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilterType(undefined)}
              className="shrink-0"
            >
              全部类型
            </Button>
            {(Object.keys(TYPE_LABELS) as NotificationType[]).map((type) => (
              <Button
                key={type}
                variant={filterType === type ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType(type)}
                className="gap-1 shrink-0"
              >
                {TYPE_ICONS[type]}
                {TYPE_LABELS[type]}
              </Button>
            ))}
          </div>

          {/* Loading */}
          {isLoading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          )}

          {/* Empty */}
          {!isLoading && notifications.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                <Inbox className="w-16 h-16 text-muted-foreground/40 mb-4" />
                <h3 className="text-lg font-medium mb-2">暂无通知</h3>
                <p className="text-sm text-muted-foreground">
                  {showUnreadOnly ? '所有通知都已读' : '暂无消息'}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Notification List (Timeline) */}
          {!isLoading && notifications.length > 0 && (
            <div className="grid gap-2">
              {notifications.map((notification) => (
                <Card
                  key={notification.id}
                  className={cn(
                    'group cursor-pointer transition-colors hover:shadow-sm duration-200',
                    !notification.is_read ? 'border-l-4 border-l-primary bg-primary/[0.02]' : 'opacity-75'
                  )}
                  onClick={() => handleNotificationClick(notification)}
                >
                  <CardContent className="py-3 px-4">
                    <div className="flex items-start gap-3">
                      {/* Type Icon */}
                      <div className="mt-0.5 shrink-0">
                        {TYPE_ICONS[notification.type] || TYPE_ICONS.info}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <h4
                            className={`text-sm font-medium truncate ${
                              !notification.is_read ? 'text-foreground' : 'text-muted-foreground'
                            }`}
                          >
                            {notification.title}
                          </h4>
                          {!notification.is_read && (
                            <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
                          )}
                        </div>
                        {notification.content && (
                          <p className="text-xs text-muted-foreground line-clamp-2">
                            {notification.content}
                          </p>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-muted-foreground">
                            {formatTime(notification.created_at)}
                          </span>
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                            {TYPE_LABELS[notification.type] || notification.type}
                          </Badge>
                        </div>
                      </div>

                      {/* Action arrow */}
                      {notification.action_url && (
                        <ExternalLink className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-1" />
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* ─── Preferences Tab ────────────────────────────── */}
        <TabsContent value="preferences" className="grid gap-6 mt-4">
          {/* Channel Toggles */}
          <Card>
            <CardContent className="py-5 space-y-4">
              <h3 className="text-base font-semibold mb-3">通知渠道</h3>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Mail className="w-5 h-5 text-muted-foreground" />
                  <Label htmlFor="email-toggle">邮件通知</Label>
                </div>
                <Switch
                  id="email-toggle"
                  checked={preferences?.email_enabled ?? true}
                  onCheckedChange={(v) => handlePreferenceToggle('email_enabled', v)}
                />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Smartphone className="w-5 h-5 text-muted-foreground" />
                  <Label htmlFor="push-toggle">推送通知</Label>
                </div>
                <Switch
                  id="push-toggle"
                  checked={preferences?.push_enabled ?? true}
                  onCheckedChange={(v) => handlePreferenceToggle('push_enabled', v)}
                />
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <MessageSquare className="w-5 h-5 text-muted-foreground" />
                  <Label htmlFor="im-toggle">IM 通知（企微/钉钉/飞书）</Label>
                </div>
                <Switch
                  id="im-toggle"
                  checked={preferences?.im_enabled ?? true}
                  onCheckedChange={(v) => handlePreferenceToggle('im_enabled', v)}
                />
              </div>
            </CardContent>
          </Card>

          {/* Quiet Hours */}
          <Card>
            <CardContent className="py-5 space-y-4">
              <div className="flex items-center gap-2 mb-1">
                <Moon className="w-5 h-5 text-muted-foreground" />
                <h3 className="text-base font-semibold">免打扰时段</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                在免打扰时段内，仅保留站内通知，不发送邮件和推送
              </p>
              <div className="flex items-center gap-3">
                <div className="space-y-1">
                  <Label htmlFor="quiet-start" className="text-xs">开始时间</Label>
                  <Input
                    id="quiet-start"
                    type="time"
                    className="w-32"
                    defaultValue={preferences?.quiet_hours_start ?? '22:00'}
                    onChange={(e) =>
                      updatePreferences.mutate({ quiet_hours_start: e.target.value })
                    }
                  />
                </div>
                <span className="text-muted-foreground mt-5">至</span>
                <div className="space-y-1">
                  <Label htmlFor="quiet-end" className="text-xs">结束时间</Label>
                  <Input
                    id="quiet-end"
                    type="time"
                    className="w-32"
                    defaultValue={preferences?.quiet_hours_end ?? '08:00'}
                    onChange={(e) =>
                      updatePreferences.mutate({ quiet_hours_end: e.target.value })
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Category Toggles */}
          <Card>
            <CardContent className="py-5 space-y-4">
              <h3 className="text-base font-semibold mb-3">通知分类</h3>
              <p className="text-sm text-muted-foreground mb-2">
                选择要接收的通知类型
              </p>

              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                <div key={key}>
                  <div className="flex items-center justify-between">
                    <Label htmlFor={`cat-${key}`}>{label}</Label>
                    <Switch
                      id={`cat-${key}`}
                      checked={preferences?.categories?.[key] ?? true}
                      onCheckedChange={(v) => handleCategoryToggle(key, v)}
                    />
                  </div>
                  {key !== Object.keys(CATEGORY_LABELS).at(-1) && (
                    <Separator className="mt-3" />
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default NotificationCenter;

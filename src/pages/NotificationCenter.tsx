import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
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
  Eye,
  EyeOff,
  Trash2,
  Clock,
  ArrowRight,
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

/** 类型 → 样式配置（现代 SaaS 风格：每种类型有自己的颜色系统） */
const TYPE_CONFIG: Record<NotificationType, {
  icon: React.ElementType;
  label: string;
  iconColor: string;
  bgColor: string;
  borderColor: string;
  badgeVariant: string;
  dotColor: string;
}> = {
  info: {
    icon: Info,
    label: '信息',
    iconColor: 'text-blue-500',
    bgColor: 'bg-blue-50/60 dark:bg-blue-950/20',
    borderColor: 'border-blue-200 dark:border-blue-800',
    badgeVariant: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    dotColor: 'bg-blue-500',
  },
  success: {
    icon: CheckCircle2,
    label: '成功',
    iconColor: 'text-emerald-500',
    bgColor: 'bg-emerald-50/60 dark:bg-emerald-950/20',
    borderColor: 'border-emerald-200 dark:border-emerald-800',
    badgeVariant: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
    dotColor: 'bg-emerald-500',
  },
  warning: {
    icon: AlertTriangle,
    label: '警告',
    iconColor: 'text-amber-500',
    bgColor: 'bg-amber-50/60 dark:bg-amber-950/20',
    borderColor: 'border-amber-200 dark:border-amber-800',
    badgeVariant: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    dotColor: 'bg-amber-500',
  },
  error: {
    icon: XCircle,
    label: '错误',
    iconColor: 'text-red-500',
    bgColor: 'bg-red-50/60 dark:bg-red-950/20',
    borderColor: 'border-red-200 dark:border-red-800',
    badgeVariant: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    dotColor: 'bg-red-500',
  },
  approval: {
    icon: FileCheck,
    label: '审批',
    iconColor: 'text-violet-500',
    bgColor: 'bg-violet-50/60 dark:bg-violet-950/20',
    borderColor: 'border-violet-200 dark:border-violet-800',
    badgeVariant: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
    dotColor: 'bg-violet-500',
  },
  system: {
    icon: Settings2,
    label: '系统',
    iconColor: 'text-slate-500',
    bgColor: 'bg-slate-50/60 dark:bg-slate-950/20',
    borderColor: 'border-slate-200 dark:border-slate-800',
    badgeVariant: 'bg-slate-100 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300',
    dotColor: 'bg-slate-500',
  },
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

function formatFullTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ─── Notification Detail Dialog ─────────────────────────────

interface NotificationDetailDialogProps {
  notification: NotificationItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onMarkRead: (id: string) => void;
  onNavigate: (url: string) => void;
}

function NotificationDetailDialog({
  notification,
  open,
  onOpenChange,
  onMarkRead,
  onNavigate,
}: NotificationDetailDialogProps) {
  if (!notification) return null;

  const config = TYPE_CONFIG[notification.type] || TYPE_CONFIG.info;
  const Icon = config.icon;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[540px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className={cn(
              'w-10 h-10 rounded-xl flex items-center justify-center shrink-0',
              config.bgColor,
            )}>
              <Icon className={cn('w-5 h-5', config.iconColor)} />
            </div>
            <div className="flex-1 min-w-0">
              <DialogTitle className="text-lg leading-snug">
                {notification.title}
              </DialogTitle>
              <DialogDescription className="flex items-center gap-2 mt-1">
                <Clock className="w-3.5 h-3.5" />
                {formatFullTime(notification.created_at)}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* 类型标签 */}
        <div className="flex items-center gap-2">
          <span className={cn(
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
            config.badgeVariant,
          )}>
            <Icon className="w-3 h-3" />
            {config.label}
          </span>
          {!notification.is_read && (
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              未读
            </span>
          )}
        </div>

        <Separator />

        {/* 消息正文 — 大字号、宽松行距 */}
        <div className="py-2">
          <p className="text-base leading-relaxed text-foreground whitespace-pre-wrap">
            {notification.content || '（无详细内容）'}
          </p>
        </div>

        <Separator />

        {/* 操作按钮栏 */}
        <div className="flex items-center justify-between gap-2 pt-1">
          <div className="flex items-center gap-2">
            {!notification.is_read && (
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => {
                  onMarkRead(notification.id);
                  toast.success('已标记为已读');
                }}
              >
                <Eye className="w-3.5 h-3.5" />
                标记已读
              </Button>
            )}
            {notification.is_read && (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <EyeOff className="w-3.5 h-3.5" />
                已读
              </span>
            )}
          </div>

          {notification.action_url && (
            <Button
              size="sm"
              className="gap-1.5"
              onClick={() => onNavigate(notification.action_url!)}
            >
              前往处理
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── Main Component ─────────────────────────────────────────

function NotificationCenter() {
  const navigate = useNavigate();
  const [filterType, setFilterType] = useState<string | undefined>(undefined);
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const [selectedNotification, setSelectedNotification] = useState<NotificationItem | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  // Realtime subscription
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

  const handleNotificationClick = (notification: NotificationItem) => {
    setSelectedNotification(notification);
    setDetailOpen(true);
    // 自动标记已读
    if (!notification.is_read) {
      markRead.mutate([notification.id]);
    }
  };

  const handleNavigateFromDialog = (url: string) => {
    setDetailOpen(false);
    if (url.startsWith('http')) {
      window.open(url, '_blank');
    } else {
      navigate(url);
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
    <div className="block px-4 md:px-0 py-2 md:py-4">
      {/* Page Header */}
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

      {/* Tabs */}
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
        <TabsContent value="notifications" className="block mt-2 md:mt-4">
          {/* Mobile mark-all-read */}
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

          {/* Type Filters */}
          <div
            className="flex items-center gap-2 overflow-x-auto pb-1 mb-3 flex-nowrap md:flex-wrap"
            style={{ scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}
          >
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
            {(Object.keys(TYPE_CONFIG) as NotificationType[]).map((type) => {
              const cfg = TYPE_CONFIG[type];
              const TypeIcon = cfg.icon;
              return (
                <Button
                  key={type}
                  variant={filterType === type ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFilterType(type)}
                  className="gap-1 shrink-0"
                >
                  <TypeIcon className={cn('w-3 h-3', filterType !== type && cfg.iconColor)} />
                  {cfg.label}
                </Button>
              );
            })}
          </div>

          {/* Loading */}
          {isLoading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          )}

          {/* Empty */}
          {!isLoading && notifications.length === 0 && (
            <div className="rounded-xl border-2 border-dashed border-muted-foreground/20 flex flex-col items-center justify-center py-16 text-center">
              <Inbox className="w-16 h-16 text-muted-foreground/30 mb-4" />
              <h3 className="text-lg font-medium mb-2 text-muted-foreground">暂无通知</h3>
              <p className="text-sm text-muted-foreground/60">
                {showUnreadOnly ? '所有通知都已读' : '暂无消息'}
              </p>
            </div>
          )}

          {/* ─── Notification List（现代 SaaS 风格卡片） ─── */}
          {!isLoading && notifications.length > 0 && (
            <div className="space-y-2 pb-6">
              {notifications.map((notification) => {
                const config = TYPE_CONFIG[notification.type] || TYPE_CONFIG.info;
                const Icon = config.icon;
                const isUnread = !notification.is_read;

                return (
                  <div
                    key={notification.id}
                    className={cn(
                      'group relative rounded-xl border p-4 cursor-pointer transition-all duration-200',
                      'hover:shadow-md hover:-translate-y-[1px]',
                      isUnread
                        ? `${config.bgColor} ${config.borderColor} border-l-[3px]`
                        : 'bg-card border-border hover:bg-accent/30',
                    )}
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <div className="flex items-start gap-3">
                      {/* 类型图标（带背景色圆角容器） */}
                      <div className={cn(
                        'w-9 h-9 rounded-lg flex items-center justify-center shrink-0 transition-transform duration-200 group-hover:scale-110',
                        isUnread ? `${config.bgColor}` : 'bg-muted',
                      )}>
                        <Icon className={cn(
                          'w-4.5 h-4.5',
                          isUnread ? config.iconColor : 'text-muted-foreground',
                        )} />
                      </div>

                      {/* 内容区 */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <h4 className={cn(
                            'text-sm truncate',
                            isUnread
                              ? 'font-semibold text-foreground'
                              : 'font-normal text-muted-foreground',
                          )}>
                            {notification.title}
                          </h4>
                          {/* 未读小圆点 */}
                          {isUnread && (
                            <span className={cn(
                              'w-2 h-2 rounded-full shrink-0 animate-pulse',
                              config.dotColor,
                            )} />
                          )}
                        </div>

                        {notification.content && (
                          <p className={cn(
                            'text-xs line-clamp-2 leading-relaxed',
                            isUnread
                              ? 'text-foreground/70'
                              : 'text-muted-foreground/70',
                          )}>
                            {notification.content}
                          </p>
                        )}

                        {/* 底部元信息 */}
                        <div className="flex items-center gap-2 mt-1.5">
                          <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatTime(notification.created_at)}
                          </span>
                          <span className={cn(
                            'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium',
                            config.badgeVariant,
                          )}>
                            {config.label}
                          </span>
                        </div>
                      </div>

                      {/* 悬停操作提示 */}
                      <div className="flex items-center gap-1 shrink-0 mt-1">
                        {notification.action_url && (
                          <ExternalLink className="w-4 h-4 text-muted-foreground/40 opacity-0 group-hover:opacity-100 transition-opacity" />
                        )}
                        <ArrowRight className="w-4 h-4 text-muted-foreground/30 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </TabsContent>

        {/* ─── Preferences Tab ────────────────────────────── */}
        <TabsContent value="preferences" className="block mt-4 space-y-6">
          {/* Channel Toggles */}
          <div className="rounded-xl border bg-card p-5 space-y-4">
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
          </div>

          {/* Quiet Hours */}
          <div className="rounded-xl border bg-card p-5 space-y-4">
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
          </div>

          {/* Category Toggles */}
          <div className="rounded-xl border bg-card p-5 space-y-4">
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
          </div>
        </TabsContent>
      </Tabs>

      {/* ─── 通知详情弹窗 ─── */}
      <NotificationDetailDialog
        notification={selectedNotification}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onMarkRead={(id) => markRead.mutate([id])}
        onNavigate={handleNavigateFromDialog}
      />
    </div>
  );
}

export default NotificationCenter;

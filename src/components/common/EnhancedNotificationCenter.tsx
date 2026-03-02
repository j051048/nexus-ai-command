/**
 * P1 UX Enhancement: Enhanced Notification Center
 * 增强版通知中心，支持分组、筛选、批量操作
 */

import React, { useState, useMemo, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Bell,
  Check,
  CheckCheck,
  Info,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  MoreHorizontal,
  Trash2,
  Settings,
  Filter,
  Clock,
  MessageSquare,
  FileCheck,
  TrendingUp,
  Gift,
  Archive,
  BellOff,
  ExternalLink,
} from 'lucide-react';
import { useNotifications, Notification } from '@/hooks/useNotifications';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { getEnterAnimationClass, getStaggerStyle } from '@/lib/animations';
import { FadeInView } from './AnimatedComponents';
import { toast } from 'sonner';

// ==================== 类型定义 ====================

type NotificationType = Notification['type'];
type NotificationCategory = 'all' | 'approval' | 'sales' | 'system' | 'reward';

interface NotificationGroup {
  date: string;
  label: string;
  notifications: Notification[];
}

interface EnhancedNotificationCenterProps {
  className?: string;
  onNotificationClick?: (notification: Notification) => void;
}

// ==================== 工具函数 ====================

const typeIcons: Record<NotificationType, React.ReactNode> = {
  success: <CheckCircle2 className="w-4 h-4 text-green-500" />,
  warning: <AlertTriangle className="w-4 h-4 text-yellow-500" />,
  error: <XCircle className="w-4 h-4 text-red-500" />,
  info: <Info className="w-4 h-4 text-blue-500" />,
};

const typeColors: Record<NotificationType, string> = {
  success: 'bg-green-500/10 border-green-500/20',
  warning: 'bg-yellow-500/10 border-yellow-500/20',
  error: 'bg-red-500/10 border-red-500/20',
  info: 'bg-blue-500/10 border-blue-500/20',
};

const categoryIcons: Record<NotificationCategory, React.ReactNode> = {
  all: <Bell className="w-4 h-4" />,
  approval: <FileCheck className="w-4 h-4" />,
  sales: <TrendingUp className="w-4 h-4" />,
  system: <Settings className="w-4 h-4" />,
  reward: <Gift className="w-4 h-4" />,
};

const categoryLabels: Record<NotificationCategory, string> = {
  all: '全部',
  approval: '审批',
  sales: '销售',
  system: '系统',
  reward: '奖励',
};

/**
 * 根据标题猜测通知类别
 */
function guessCategory(notification: Notification): NotificationCategory {
  const title = notification.title.toLowerCase();
  const content = (notification.content || '').toLowerCase();
  const combined = title + content;

  if (combined.includes('审批') || combined.includes('报销') || combined.includes('申请')) {
    return 'approval';
  }
  if (combined.includes('销售') || combined.includes('商机') || combined.includes('客户')) {
    return 'sales';
  }
  if (combined.includes('奖励') || combined.includes('积分') || combined.includes('徽章')) {
    return 'reward';
  }
  return 'system';
}

/**
 * 按日期分组通知
 */
function groupNotificationsByDate(notifications: Notification[]): NotificationGroup[] {
  const groups: Map<string, Notification[]> = new Map();
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();

  notifications.forEach((notif) => {
    const date = new Date(notif.created_at).toDateString();
    let label: string;

    if (date === today) {
      label = '今天';
    } else if (date === yesterday) {
      label = '昨天';
    } else {
      label = new Date(notif.created_at).toLocaleDateString('zh-CN', {
        month: 'long',
        day: 'numeric',
      });
    }

    const key = `${date}_${label}`;
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(notif);
  });

  return Array.from(groups.entries()).map(([key, notifs]) => ({
    date: key.split('_')[0],
    label: key.split('_')[1],
    notifications: notifs,
  }));
}

// ==================== 子组件 ====================

interface NotificationItemProps {
  notification: Notification;
  selected: boolean;
  onSelect: (id: string, selected: boolean) => void;
  onRead: (id: string) => void;
  onDelete: (id: string) => void;
  onClick?: (notification: Notification) => void;
  index: number;
}

function NotificationItem({
  notification,
  selected,
  onSelect,
  onRead,
  onDelete,
  onClick,
  index,
}: NotificationItemProps) {
  const category = guessCategory(notification);

  return (
    <div
      className={cn(
        'group relative p-3 rounded-lg transition-all cursor-pointer',
        'hover:bg-muted/50',
        !notification.is_read && 'bg-primary/5',
        selected && 'ring-2 ring-primary/50',
        getEnterAnimationClass('fade', 'fast')
      )}
      style={getStaggerStyle(index, 0, 30)}
      onClick={() => {
        if (!notification.is_read) {
          onRead(notification.id);
        }
        onClick?.(notification);
      }}
    >
      {/* Selection Checkbox */}
      <div
        className={cn(
          'absolute left-2 top-3 transition-opacity',
          'opacity-0 group-hover:opacity-100',
          selected && 'opacity-100'
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <Checkbox
          checked={selected}
          onCheckedChange={(checked) => onSelect(notification.id, !!checked)}
        />
      </div>

      <div className={cn('flex gap-3', selected && 'pl-6')}>
        {/* Icon */}
        <div
          className={cn(
            'w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 border',
            typeColors[notification.type]
          )}
        >
          {typeIcons[notification.type]}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p
                  className={cn(
                    'text-sm font-medium truncate',
                    notification.is_read ? 'text-muted-foreground' : 'text-foreground'
                  )}
                >
                  {notification.title}
                </p>
                {!notification.is_read && (
                  <span className="w-2 h-2 rounded-full bg-primary flex-shrink-0" />
                )}
              </div>
              <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                {notification.content}
              </p>
            </div>

            {/* Actions */}
            <div
              className={cn(
                'flex items-center gap-1 transition-opacity',
                'opacity-0 group-hover:opacity-100'
              )}
              onClick={(e) => e.stopPropagation()}
            >
              {notification.action_url && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => window.open(notification.action_url, '_blank')}
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                </Button>
              )}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-7 w-7">
                    <MoreHorizontal className="w-3.5 h-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {!notification.is_read && (
                    <DropdownMenuItem onClick={() => onRead(notification.id)}>
                      <Check className="w-4 h-4 mr-2" />
                      标为已读
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem>
                    <Archive className="w-4 h-4 mr-2" />
                    归档
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => onDelete(notification.id)}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center gap-2 mt-2">
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4">
              {categoryIcons[category]}
              <span className="ml-1">{categoryLabels[category]}</span>
            </Badge>
            <span className="text-[10px] text-muted-foreground">
              {formatDistanceToNow(new Date(notification.created_at), {
                addSuffix: true,
                locale: zhCN,
              })}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== 空状态组件 ====================

function EmptyNotifications({ category }: { category: NotificationCategory }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-4">
        <BellOff className="w-8 h-8 text-muted-foreground/50" />
      </div>
      <p className="text-sm font-medium text-muted-foreground">
        {category === 'all' ? '暂无通知' : `暂无${categoryLabels[category]}通知`}
      </p>
      <p className="text-xs text-muted-foreground/70 mt-1">
        新消息将在这里显示
      </p>
    </div>
  );
}

// ==================== 主组件 ====================

export function EnhancedNotificationCenter({
  className,
  onNotificationClick,
}: EnhancedNotificationCenterProps) {
  const { notifications, unreadCount, markAsRead, markAllAsRead, deleteNotification, deleteNotifications } = useNotifications();
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<NotificationCategory>('all');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // 按类别筛选
  const filteredNotifications = useMemo(() => {
    if (activeTab === 'all') return notifications;
    return notifications.filter(
      (notif) => guessCategory(notif) === activeTab
    );
  }, [notifications, activeTab]);

  // 按日期分组
  const groupedNotifications = useMemo(
    () => groupNotificationsByDate(filteredNotifications),
    [filteredNotifications]
  );

  // 各类别未读数
  const categoryUnreadCounts = useMemo(() => {
    const counts: Record<NotificationCategory, number> = {
      all: 0,
      approval: 0,
      sales: 0,
      system: 0,
      reward: 0,
    };

    notifications
      .filter((n) => !n.is_read)
      .forEach((n) => {
        counts.all++;
        counts[guessCategory(n)]++;
      });

    return counts;
  }, [notifications]);

  // 选择操作
  const handleSelect = useCallback((id: string, selected: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (selected) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    if (selectedIds.size === filteredNotifications.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredNotifications.map((n) => n.id)));
    }
  }, [filteredNotifications, selectedIds.size]);

  // 批量操作
  const handleBatchRead = useCallback(() => {
    selectedIds.forEach((id) => markAsRead.mutate(id));
    setSelectedIds(new Set());
    toast.success(`已将 ${selectedIds.size} 条通知标为已读`);
  }, [selectedIds, markAsRead]);

  const handleBatchDelete = useCallback(() => {
    const ids = Array.from(selectedIds);
    deleteNotifications.mutate(ids, {
      onSuccess: () => {
        toast.success(`已删除 ${ids.length} 条通知`);
        setSelectedIds(new Set());
      },
      onError: () => {
        toast.error('批量删除失败，请重试');
      },
    });
  }, [selectedIds, deleteNotifications]);

  const handleRead = useCallback(
    (id: string) => {
      markAsRead.mutate(id);
    },
    [markAsRead]
  );

  const handleDelete = useCallback((id: string) => {
    deleteNotification.mutate(id, {
      onSuccess: () => {
        toast.success('通知已删除');
      },
      onError: () => {
        toast.error('删除失败，请重试');
      },
    });
  }, [deleteNotification]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'relative hover:bg-muted rounded-full',
            className
          )}
        >
          <Bell className="w-5 h-5 text-muted-foreground hover:text-foreground transition-colors" />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center">
              <span className="absolute inline-flex h-4 w-4 rounded-full bg-destructive opacity-75 animate-ping" />
              <Badge
                variant="destructive"
                className="relative h-4 min-w-4 px-1 text-[10px] font-bold"
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </Badge>
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent
        className="w-[380px] p-0"
        align="end"
        sideOffset={8}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-card">
          <div>
            <h4 className="text-sm font-semibold">通知中心</h4>
            <p className="text-xs text-muted-foreground">
              {unreadCount > 0 ? `${unreadCount} 条未读消息` : '所有消息已读'}
            </p>
          </div>
          <div className="flex items-center gap-1">
            {selectedIds.size > 0 ? (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2 text-xs"
                  onClick={handleBatchRead}
                >
                  <Check className="w-3 h-3 mr-1" />
                  已读
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2 text-xs text-destructive hover:text-destructive"
                  onClick={handleBatchDelete}
                >
                  <Trash2 className="w-3 h-3 mr-1" />
                  删除
                </Button>
              </>
            ) : (
              unreadCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2 text-xs"
                  onClick={() => markAllAsRead.mutate()}
                >
                  <CheckCheck className="w-3 h-3 mr-1" />
                  全部已读
                </Button>
              )
            )}
          </div>
        </div>

        {/* Tabs */}
        <Tabs
          value={activeTab}
          onValueChange={(v) => {
            setActiveTab(v as NotificationCategory);
            setSelectedIds(new Set());
          }}
        >
          <div className="border-b px-2">
            <TabsList className="h-10 w-full justify-start bg-transparent p-0">
              {(Object.keys(categoryLabels) as NotificationCategory[]).map(
                (category) => (
                  <TabsTrigger
                    key={category}
                    value={category}
                    className={cn(
                      'relative h-10 rounded-none border-b-2 border-transparent px-3 text-xs',
                      'data-[state=active]:border-primary data-[state=active]:bg-transparent'
                    )}
                  >
                    {categoryLabels[category]}
                    {categoryUnreadCounts[category] > 0 && (
                      <Badge
                        variant="secondary"
                        className="ml-1.5 h-4 min-w-4 px-1 text-[10px]"
                      >
                        {categoryUnreadCounts[category]}
                      </Badge>
                    )}
                  </TabsTrigger>
                )
              )}
            </TabsList>
          </div>

          {/* Selection Bar */}
          {filteredNotifications.length > 0 && (
            <div className="flex items-center justify-between px-4 py-2 bg-muted/30 border-b">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={
                    selectedIds.size === filteredNotifications.length &&
                    filteredNotifications.length > 0
                  }
                  onCheckedChange={handleSelectAll}
                />
                <span className="text-xs text-muted-foreground">
                  {selectedIds.size > 0
                    ? `已选 ${selectedIds.size} 项`
                    : '全选'}
                </span>
              </div>
              <span className="text-xs text-muted-foreground">
                共 {filteredNotifications.length} 条
              </span>
            </div>
          )}

          {/* Content */}
          <TabsContent value={activeTab} className="m-0">
            <ScrollArea className="h-[360px]">
              {filteredNotifications.length === 0 ? (
                <EmptyNotifications category={activeTab} />
              ) : (
                <div className="p-2 space-y-4">
                  {groupedNotifications.map((group) => (
                    <div key={group.date}>
                      <div className="sticky top-0 bg-popover/95 backdrop-blur-sm px-2 py-1 z-10">
                        <span className="text-xs font-medium text-muted-foreground">
                          {group.label}
                        </span>
                      </div>
                      <div className="space-y-1">
                        {group.notifications.map((notif, index) => (
                          <NotificationItem
                            key={notif.id}
                            notification={notif}
                            selected={selectedIds.has(notif.id)}
                            onSelect={handleSelect}
                            onRead={handleRead}
                            onDelete={handleDelete}
                            onClick={onNotificationClick}
                            index={index}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </TabsContent>
        </Tabs>

        {/* Footer */}
        <div className="flex items-center justify-between p-3 border-t bg-muted/30">
          <Button variant="ghost" size="sm" className="h-8 text-xs">
            <Settings className="w-3 h-3 mr-1.5" />
            通知设置
          </Button>
          <Button variant="ghost" size="sm" className="h-8 text-xs">
            查看全部
            <ExternalLink className="w-3 h-3 ml-1.5" />
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export default EnhancedNotificationCenter;
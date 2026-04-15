import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Bell,
  Clock,
  ExternalLink,
  Trash2,
  Check,
  Info,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  FileCheck,
  Settings,
} from 'lucide-react';
import { Notification } from '@/hooks/useNotifications';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { cn } from '@/lib/utils';

interface NotificationDetailDialogProps {
  notification: Notification | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRead: (id: string) => void;
  onDelete: (id: string) => void;
  onNavigate: (url: string) => void;
}

const typeIcons: Record<string, React.ReactNode> = {
  success: <CheckCircle2 className="w-6 h-6 text-green-500" />,
  warning: <AlertTriangle className="w-6 h-6 text-yellow-500" />,
  error: <XCircle className="w-6 h-6 text-red-500" />,
  info: <Info className="w-6 h-6 text-blue-500" />,
  approval: <FileCheck className="w-6 h-6 text-orange-500" />,
  system: <Settings className="w-6 h-6 text-gray-500" />,
};

const typeColors: Record<string, string> = {
  success: 'bg-green-500/10 border-green-500/20',
  warning: 'bg-yellow-500/10 border-yellow-500/20',
  error: 'bg-red-500/10 border-red-500/20',
  info: 'bg-blue-500/10 border-blue-500/20',
  approval: 'bg-orange-500/10 border-orange-500/20',
  system: 'bg-gray-500/10 border-gray-500/20',
};

export function NotificationDetailDialog({
  notification,
  open,
  onOpenChange,
  onRead,
  onDelete,
  onNavigate,
}: NotificationDetailDialogProps) {
  if (!notification) return null;

  const handleAction = () => {
    if (notification.action_url) {
      onOpenChange(false);
      if (notification.action_url.startsWith('http')) {
        window.open(notification.action_url, '_blank');
      } else {
        onNavigate(notification.action_url);
      }
    }
  };

  const handleDelete = () => {
    onDelete(notification.id);
    onOpenChange(false);
  };

  const handleRead = () => {
    if (!notification.is_read) {
      onRead(notification.id);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] gap-0 p-0 overflow-hidden rounded-2xl border border-border/50 card-glass">
        <div className={cn("p-6 flex items-start gap-4 border-b", typeColors[notification.type])}>
          <div className="p-3 rounded-2xl bg-background/50 border border-border/50 shadow-sm">
            {typeIcons[notification.type]}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-xl font-bold text-foreground leading-tight mb-2">
              {notification.title}
            </h2>
            <div className="flex items-center gap-3 text-xs text-muted-foreground font-medium">
              <span className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true, locale: zhCN })}
              </span>
              <span className="flex items-center gap-1.5">
                <div className={cn("w-2 h-2 rounded-full", notification.is_read ? 'bg-muted-foreground/30' : 'bg-primary')} />
                {notification.is_read ? '已阅读' : '未读消息'}
              </span>
            </div>
          </div>
        </div>

        <ScrollArea className="max-h-[400px] p-6">
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <p className="text-base text-foreground leading-relaxed whitespace-pre-wrap">
              {notification.content}
            </p>
          </div>

          {notification.metadata && Object.keys(notification.metadata).length > 0 && (
            <div className="mt-8 pt-6 border-t border-border/50">
              <h4 className="text-sm font-bold text-foreground mb-4 flex items-center gap-2">
                <div className="w-1 h-4 bg-primary rounded-full"></div>
                关联数据
              </h4>
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(notification.metadata).map(([key, val]) => (
                  <div key={key} className="bg-muted/30 p-3 rounded-xl border border-border/30">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 font-mono">{key}</p>
                    <p className="text-sm font-semibold text-foreground truncate">{String(val)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </ScrollArea>

        <DialogFooter className="p-4 bg-muted/20 border-t flex flex-row items-center justify-between sm:justify-between gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDelete}
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            删除
          </Button>

          <div className="flex items-center gap-2">
            {!notification.is_read && (
              <Button variant="outline" size="sm" onClick={handleRead}>
                <Check className="w-4 h-4 mr-2" />
                标为已读
              </Button>
            )}
            {notification.action_url ? (
              <Button size="sm" onClick={handleAction} className="glow-primary">
                立即处理
                <ExternalLink className="w-4 h-4 ml-2" />
              </Button>
            ) : (
              <Button variant="secondary" size="sm" onClick={() => onOpenChange(false)}>
                知道了
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

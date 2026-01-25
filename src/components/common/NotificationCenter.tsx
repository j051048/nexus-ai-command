import React, { useState } from 'react';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Bell, Check, Info, AlertTriangle, XCircle, CheckCircle2 } from 'lucide-react';
import { useNotifications, Notification } from '@/hooks/useNotifications';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';

export function NotificationCenter() {
    const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotifications();
    const [open, setOpen] = useState(false);

    const getIcon = (type: Notification['type']) => {
        switch (type) {
            case 'success': return <CheckCircle2 className="w-4 h-4 text-success" />;
            case 'warning': return <AlertTriangle className="w-4 h-4 text-warning" />;
            case 'error': return <XCircle className="w-4 h-4 text-destructive" />;
            default: return <Info className="w-4 h-4 text-primary" />;
        }
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" className="relative hover:bg-muted rounded-full">
                    <Bell className="w-5 h-5 text-muted-foreground hover:text-foreground transition-colors" />
                    {unreadCount > 0 && (
                        <span className="absolute top-2 right-2 flex h-2.5 w-2.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-destructive opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-destructive"></span>
                        </span>
                    )}
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-80 p-0" align="end" sideOffset={8}>
                <div className="flex items-center justify-between p-4 border-b border-border bg-card">
                    <div className="space-y-1">
                        <h4 className="text-sm font-semibold text-foreground">通知中心</h4>
                        <p className="text-xs text-muted-foreground">实时消息推送</p>
                    </div>
                    {unreadCount > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs h-7 px-2 hover:bg-secondary text-muted-foreground hover:text-foreground"
                            onClick={() => markAllAsRead.mutate()}
                        >
                            <Check className="w-3 h-3 mr-1" />
                            全部已读
                        </Button>
                    )}
                </div>
                <ScrollArea className="h-[320px] bg-card">
                    {notifications.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-40 text-muted-foreground/50">
                            <Bell className="w-10 h-10 mb-3 opacity-20" />
                            <p className="text-sm">暂无新通知</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-border">
                            {notifications.map((notif) => (
                                <div
                                    key={notif.id}
                                    className={cn(
                                        "p-4 hover:bg-secondary/50 transition-colors cursor-pointer relative group",
                                        !notif.read && "bg-primary/5" // Highlight unread
                                    )}
                                    onClick={() => !notif.read && markAsRead.mutate(notif.id)}
                                >
                                    <div className="flex gap-3 items-start">
                                        <div className="mt-0.5 flex-shrink-0">{getIcon(notif.type)}</div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-start justify-between gap-2 mb-1">
                                                <p className={cn("text-sm font-medium leading-none truncate", !notif.read ? "text-foreground" : "text-muted-foreground")}>
                                                    {notif.title}
                                                </p>
                                                {!notif.read && (
                                                    <span className="w-2 h-2 rounded-full bg-primary flex-shrink-0 mt-1" />
                                                )}
                                            </div>
                                            <p className="text-xs text-muted-foreground line-clamp-2 break-all mb-1.5">
                                                {notif.message}
                                            </p>
                                            <p className="text-[10px] text-muted-foreground/70">
                                                {formatDistanceToNow(new Date(notif.created_at), { addSuffix: true, locale: zhCN })}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </ScrollArea>
            </PopoverContent>
        </Popover>
    );
}

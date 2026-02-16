import React, { useState } from 'react';
import { Bell } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { useNotifications } from '@/hooks/useNotifications';
import { cn } from '@/lib/utils';

export function NotificationBell() {
    const [showNotifications, setShowNotifications] = useState(false);
    const { notifications, unreadCount } = useNotifications();

    return (
        <>
            <Button
                variant="outline"
                size="icon"
                className="relative"
                onClick={() => setShowNotifications(true)}
            >
                <Bell className="w-5 h-5" />
                {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-white text-xs rounded-full flex items-center justify-center">
                        {unreadCount}
                    </span>
                )}
            </Button>

            <Dialog open={showNotifications} onOpenChange={setShowNotifications}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>通知中心</DialogTitle>
                    </DialogHeader>
                    <div className="max-h-96 overflow-y-auto space-y-2 pr-1">
                        {!notifications || notifications.length === 0 ? (
                            <p className="text-center text-muted-foreground py-8">暂无通知</p>
                        ) : (
                            notifications.map((notification) => (
                                <div
                                    key={notification.id}
                                    className={cn(
                                        "p-3 rounded-lg border transition-all hover:bg-secondary/50",
                                        notification.read ? "bg-secondary/10 border-border" : "bg-primary/5 border-primary/20 shadow-sm"
                                    )}
                                >
                                    <p className="font-semibold text-foreground text-sm">{notification.title}</p>
                                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{notification.message}</p>
                                    <p className="text-[10px] text-muted-foreground mt-2">
                                        {new Date(notification.created_at).toLocaleString('zh-CN')}
                                    </p>
                                </div>
                            ))
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
}

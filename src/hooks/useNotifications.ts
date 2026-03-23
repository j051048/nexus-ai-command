import { useEffect, useState } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

export interface Notification {
    id: string;
    user_id: string;
    type: 'info' | 'success' | 'warning' | 'error' | 'approval' | 'system';
    title: string;
    content: string;
    is_read: boolean;
    action_url?: string;
    created_at: string;
}

export function useNotificationsRealtime() {
    const { user } = useAuth();
    const queryClient = useQueryClient();
    useEffect(() => {
        if (!user?.id) return;

        const channel = supabase
            .channel('notifications-realtime')
            .on(
                'postgres_changes',
                {
                    event: 'INSERT',
                    schema: 'public',
                    table: 'notifications',
                    filter: `user_id=eq.${user.id}`,
                },
                (payload) => {
                    const newNotif = payload.new as Notification;
                    newNotif.type === 'error' ? toast.error(newNotif.title, { description: newNotif.content }) : toast.success(newNotif.title, { description: newNotif.content });
                    queryClient.invalidateQueries({ queryKey: ['notifications'] });
                    queryClient.invalidateQueries({ queryKey: ['notification-center'] });
                    queryClient.invalidateQueries({ queryKey: ['notification-unread-count'] });
                }
            )
            .subscribe();

        return () => {
            channel.unsubscribe();
        };
    }, [user?.id, queryClient]);
}

export function useNotifications() {
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const [unreadCount, setUnreadCount] = useState(0);

    // Fetch Notifications
    const { data: notifications = [] } = useQuery({
        queryKey: ['notifications', user?.id],
        queryFn: async () => {
            if (!user?.id) return [];
            const { data, error } = await supabase
                .from('notifications')
                .select('*')
                .eq('user_id', user.id)
                .order('created_at', { ascending: false })
                .limit(20);

            if (error) throw error;
            return data as Notification[];
        },
        enabled: !!user?.id,
    });

    useEffect(() => {
        setUnreadCount(notifications.filter(n => !n.is_read).length);
    }, [notifications]);

    const markAsRead = useMutation({
        mutationFn: async (id: string) => {
            const { error } = await supabase
                .from('notifications')
                .update({ is_read: true })
                .eq('id', id);
            if (error) throw error;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications'] });
            queryClient.invalidateQueries({ queryKey: ['notification-unread-count'] });
        },
    });

    const markAllAsRead = useMutation({
        mutationFn: async () => {
            if (!user?.id) return;
            const { error } = await supabase
                .from('notifications')
                .update({ is_read: true })
                .eq('user_id', user.id)
                .eq('is_read', false);
            if (error) throw error;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications'] });
            queryClient.invalidateQueries({ queryKey: ['notification-unread-count'] });
        },
    });

    const deleteNotification = useMutation({
        mutationFn: async (id: string) => {
            const { error } = await supabase
                .from('notifications')
                .delete()
                .eq('id', id);
            if (error) throw error;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications'] });
        },
    });

    const deleteNotifications = useMutation({
        mutationFn: async (ids: string[]) => {
            const { error } = await supabase
                .from('notifications')
                .delete()
                .in('id', ids);
            if (error) throw error;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications'] });
        },
    });

    return {
        notifications,
        unreadCount,
        markAsRead,
        markAllAsRead,
        deleteNotification,
        deleteNotifications,
    };
}

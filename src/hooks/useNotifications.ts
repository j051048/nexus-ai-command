import { useEffect, useState } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/hooks/use-toast';

export interface Notification {
    id: string;
    user_id: string;
    type: 'info' | 'success' | 'warning' | 'error';
    title: string;
    message: string;
    read: boolean;
    link?: string;
    created_at: string;
}

export function useNotifications() {
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const { toast } = useToast();
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

    // Calculate unread count locally for immediate feedback
    useEffect(() => {
        setUnreadCount(notifications.filter(n => !n.read).length);
    }, [notifications]);

    // Mark as Read Mutation
    const markAsRead = useMutation({
        mutationFn: async (id: string) => {
            const { error } = await supabase
                .from('notifications')
                .update({ read: true })
                .eq('id', id);
            if (error) throw error;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications'] });
        },
    });

    // Mark All as Read Mutation
    const markAllAsRead = useMutation({
        mutationFn: async () => {
            if (!user?.id) return;
            const { error } = await supabase
                .from('notifications')
                .update({ read: true })
                .eq('user_id', user.id)
                .eq('read', false); // Optimization
            if (error) throw error;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications'] });
        },
    });

    // Real-time Subscription
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
                    console.log('New notification:', payload);
                    const newNotif = payload.new as Notification;

                    // Show Toast
                    toast({
                        title: newNotif.title,
                        description: newNotif.message,
                        variant: newNotif.type === 'error' ? 'destructive' : 'default', // Map specific types if needed
                    });

                    // Invalidate query to refresh list
                    queryClient.invalidateQueries({ queryKey: ['notifications'] });
                }
            )
            .subscribe();

        return () => {
            supabase.removeChannel(channel);
        };
    }, [user?.id, queryClient, toast]);

    return {
        notifications,
        unreadCount,
        markAsRead,
        markAllAsRead,
    };
}

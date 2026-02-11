import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { SalesLead } from '@/types/nexus';
import { salesLeadSchema } from '@/lib/schemas';

// 定义表名常量以避免 any
const SALES_LEADS_TABLE = 'sales_leads' as any;

export function useSalesLeads() {
    const { session } = useAuth();
    const queryClient = useQueryClient();

    // 获取所有线索
    const { profile } = useAuth();
    const { data: leads = [], isLoading } = useQuery({
        queryKey: ['sales-leads', profile?.organization_id],
        queryFn: async () => {
            if (!session?.user?.id || !profile?.organization_id) return [];

            let query = supabase
                .from(SALES_LEADS_TABLE)
                .select('*');

            if (profile?.organization_id) {
                query = query.eq('organization_id', profile.organization_id);
            } else {
                query = query.eq('user_id', session?.user?.id);
            }

            query = query.order('score', { ascending: false });

            const { data, error } = await query;

            if (error) {
                console.error('Error fetching leads:', error);
                return [];
            }

            // 数据屏蔽层：使用 Zod 验证并提供默认值
            return (data || []).map(item => {
                const result = salesLeadSchema.safeParse(item);
                if (!result.success) {
                    console.warn('Invalid lead data found:', result.error);
                }
                // 即便失败也返回原始数据（或默认值），确保 UI 不崩溃
                return (result.success ? result.data : item) as SalesLead;
            });
        },
        enabled: !!session?.user?.id && !!profile?.organization_id,
    });

    // 更新线索阶段
    const updateLeadStage = useMutation({
        mutationFn: async ({ id, stage }: { id: string; stage: SalesLead['stage'] }) => {
            const { error } = await supabase
                .from(SALES_LEADS_TABLE)
                .update({ stage })
                .eq('id', id);

            if (error) throw error;
            return { id, stage };
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['sales-leads'] });
        },
    });

    return {
        leads,
        isLoading,
        updateLeadStage,
    };
}

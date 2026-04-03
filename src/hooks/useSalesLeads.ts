import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { SalesLead } from '@/types/nexus';
import { salesLeadSchema } from '@/lib/schemas';
import { httpClient } from '@/lib/httpClient';

// 定义表名常量
const SALES_LEADS_TABLE = 'sales_leads';

export function useSalesLeads() {
    const { session } = useAuth();
    const queryClient = useQueryClient();

    // 获取所有线索
    const { profile } = useAuth();
    const { data: leads = [], isLoading } = useQuery({
        queryKey: ['sales-leads', profile?.organization_id],
        queryFn: async () => {
            if (!session?.user?.id || !profile?.organization_id) return [];

            const response = await httpClient.get('/api/sales-leads');
            const data = Array.isArray(response.data?.leads) ? response.data.leads : [];

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
            await httpClient.put(`/api/sales-leads/${id}`, { stage });
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

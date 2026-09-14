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
    const { data: leads = [], isLoading, error, refetch } = useQuery({
        queryKey: ['sales-leads', profile?.organization_id],
        queryFn: async () => {
            if (!session?.user?.id || !profile?.organization_id) return [];

            const response = await httpClient.get<{ leads: unknown[] }>('/api/sales-leads');
            const data = Array.isArray(response.data?.leads) ? response.data.leads : [];

            // 数据屏蔽层：使用 Zod 验证并提供默认值
            return (data || []).map(item => {
                const result = salesLeadSchema.safeParse(item);
                if (!result.success) throw new Error('线索数据格式异常，请刷新或联系管理员');
                const lead = result.data;
                return {
                    id: lead.id, name: lead.name, company: lead.company || '',
                    title: lead.title || '', score: lead.score, stage: lead.stage,
                    aiSuggestion: lead.ai_suggestion || '', winProbability: lead.win_probability,
                    lastContact: lead.last_contact && Number.isFinite(Date.parse(lead.last_contact))
                        ? new Date(lead.last_contact) : undefined,
                } satisfies SalesLead;
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
        error,
        refetch,
        updateLeadStage,
    };
}

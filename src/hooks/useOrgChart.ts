/**
 * useOrgChart - 组织架构管理 hooks
 * 获取组织成员列表、更新汇报关系
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';

// ─── Types ──────────────────────────────────────────────────

export interface OrgMember {
  id: string;
  full_name: string;
  department: string;
  role: string;
  manager_id: string | null;
  manager_name: string | null;
  avatar_url: string | null;
}

// ─── Hooks ──────────────────────────────────────────────────

export function useOrgMembers() {
  return useQuery({
    queryKey: ['org-members'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: OrgMember[] }>(
        'api/organization/members'
      );
      return res.data || [];
    },
    staleTime: 30_000,
  });
}

export function useUpdateManager() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, managerId }: { userId: string; managerId: string | null }) => {
      const res = await aiClient.fetch<{ success: boolean; data: { user_id: string; manager_id: string | null } }>(
        `api/organization/members/${userId}/manager`,
        {
          method: 'PUT',
          body: JSON.stringify({ manager_id: managerId }),
        }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-members'] });
      toast.success('汇报关系已更新');
    },
    onError: (err: Error) => {
      toast.error(err.message || '更新汇报关系失败');
    },
  });
}

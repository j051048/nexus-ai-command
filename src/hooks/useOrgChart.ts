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

// ─── Department Types ────────────────────────────────────────

export interface OrgDepartment {
  id: string;
  name: string;
  parent_id: string | null;
  manager_id: string | null;
  sort_order: number;
}

// ─── Department Hooks ────────────────────────────────────────

export function useDepartments() {
  return useQuery({
    queryKey: ['org-departments'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: OrgDepartment[] }>(
        'api/org-structure/departments'
      );
      return res.data || [];
    },
    staleTime: 30_000,
  });
}

export function useCreateDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; parent_id?: string | null }) => {
      const res = await aiClient.fetch<{ success: boolean; data: OrgDepartment }>(
        'api/org-structure/departments',
        { method: 'POST', body: JSON.stringify(body) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-departments'] });
      queryClient.invalidateQueries({ queryKey: ['org-members'] });
      toast.success('部门创建成功');
    },
    onError: (err: Error) => {
      toast.error(err.message || '创建部门失败');
    },
  });
}

export function useUpdateDepartmentParent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ deptId, parentId }: { deptId: string; parentId: string | null }) => {
      const res = await aiClient.fetch<{ success: boolean; data: OrgDepartment }>(
        `api/org-structure/departments/${deptId}`,
        { method: 'PATCH', body: JSON.stringify({ parent_id: parentId }) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-departments'] });
      toast.success('部门层级已更新');
    },
    onError: (err: Error) => {
      toast.error(err.message || '更新部门层级失败');
    },
  });
}

export function useTransferEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ employeeId, departmentId }: { employeeId: string; departmentId: string }) => {
      const res = await aiClient.fetch<{ success: boolean }>(
        `api/org-structure/employees/${employeeId}`,
        { method: 'PATCH', body: JSON.stringify({ department_id: departmentId }) }
      );
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-members'] });
      queryClient.invalidateQueries({ queryKey: ['org-departments'] });
      toast.success('人员调动成功');
    },
    onError: (err: Error) => {
      toast.error(err.message || '人员调动失败');
    },
  });
}

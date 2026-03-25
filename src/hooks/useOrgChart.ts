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

// 安全提取字符串（防止 API 返回对象导致 React #301）
function ensureStr(v: unknown, field?: string): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  console.warn(`[useOrgChart] field "${field}" is not a string:`, typeof v, v);
  if (typeof v === 'object') {
    const name = (v as Record<string, unknown>).name;
    if (typeof name === 'string') return name;
    return JSON.stringify(v);
  }
  return String(v);
}

// 清洗 OrgMember 数据，确保所有字段类型安全
function sanitizeMember(raw: Record<string, unknown>): OrgMember {
  return {
    id: ensureStr(raw.id, 'id'),
    full_name: ensureStr(raw.full_name, 'full_name'),
    department: ensureStr(raw.department, 'department'),
    role: ensureStr(raw.role, 'role') || 'employee',
    manager_id: raw.manager_id != null ? ensureStr(raw.manager_id, 'manager_id') : null,
    manager_name: raw.manager_name != null ? ensureStr(raw.manager_name, 'manager_name') : null,
    avatar_url: typeof raw.avatar_url === 'string' ? raw.avatar_url : null,
  };
}

// ─── Hooks ──────────────────────────────────────────────────

export function useOrgMembers() {
  return useQuery({
    queryKey: ['org-members'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: unknown[] }>(
        'api/organization/members'
      );
      const raw = res.data;
      if (!Array.isArray(raw)) return [];
      return raw.map((m) => sanitizeMember(m as Record<string, unknown>));
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

// 清洗 OrgDepartment 数据
function sanitizeDepartment(raw: Record<string, unknown>): OrgDepartment {
  return {
    id: ensureStr(raw.id, 'dept.id'),
    name: ensureStr(raw.name, 'dept.name'),
    parent_id: raw.parent_id != null ? ensureStr(raw.parent_id, 'dept.parent_id') : null,
    manager_id: raw.manager_id != null ? ensureStr(raw.manager_id, 'dept.manager_id') : null,
    sort_order: typeof raw.sort_order === 'number' ? raw.sort_order : 0,
  };
}

// ─── Department Hooks ────────────────────────────────────────

export function useDepartments() {
  return useQuery({
    queryKey: ['org-departments'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { departments: unknown[] } | unknown[] }>(
        'api/org-structure/departments'
      );
      // 后端返回 { data: { departments: [...] } }，需从嵌套对象中提取数组
      const raw = res.data;
      let arr: unknown[];
      if (Array.isArray(raw)) {
        arr = raw;
      } else if (raw && typeof raw === 'object' && 'departments' in raw) {
        arr = (raw as { departments: unknown[] }).departments;
      } else {
        arr = [];
      }
      if (!Array.isArray(arr)) return [];
      return arr.map((d) => sanitizeDepartment(d as Record<string, unknown>));
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

export function useUpdateDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ 
      deptId, 
      name, 
      managerId, 
      parentId 
    }: { 
      deptId: string; 
      name?: string; 
      managerId?: string | null; 
      parentId?: string | null 
    }) => {
      const body: Record<string, unknown> = {};
      if (name !== undefined) body.name = name;
      if (managerId !== undefined) body.manager_id = managerId;
      if (parentId !== undefined) body.parent_id = parentId;

      const res = await aiClient.fetch<{ success: boolean; data: OrgDepartment }>(
        `api/org-structure/departments/${deptId}`,
        { method: 'PATCH', body: JSON.stringify(body) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-departments'] });
      queryClient.invalidateQueries({ queryKey: ['org-members'] });
      toast.success('部门信息已更新');
    },
    onError: (err: Error) => {
      toast.error(err.message || '更新部门失败');
    },
  });
}

export function useDeleteDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (deptId: string) => {
      // 软删除：通过 PATCH 设置 status=dissolved（兼容后端无 DELETE 端点的情况）
      await aiClient.fetch(`api/org-structure/departments/${deptId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'dissolved' }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-departments'] });
      toast.success('部门已删除');
    },
    onError: (err: Error) => {
      toast.error(err.message || '删除部门失败');
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

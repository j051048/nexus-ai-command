import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import type { FormField } from '@/components/forms/DynamicFormRenderer';

// ─── 类型定义 ──────────────────────────────────────────────

export interface FormSchema {
  id: string;
  name: string;
  approval_type: string;
  fields: FormField[];
  created_at?: string;
  updated_at?: string;
}

interface CreateFormSchemaPayload {
  name: string;
  approval_type: string;
  fields: FormField[];
}

interface UpdateFormSchemaPayload {
  id: string;
  name: string;
  approval_type: string;
  fields: FormField[];
}

// ─── Hooks ──────────────────────────────────────────────────

/**
 * 获取所有表单 schema 列表
 */
export function useFormSchemas() {
  return useQuery<FormSchema[]>({
    queryKey: ['form-schemas'],
    queryFn: () =>
      aiClient.fetch<FormSchema[]>('api/form-schemas'),
  });
}

/**
 * 获取单个表单 schema
 */
export function useFormSchema(id: string) {
  return useQuery<FormSchema>({
    queryKey: ['form-schemas', id],
    queryFn: () =>
      aiClient.fetch<FormSchema>(`api/form-schemas/${id}`),
    enabled: !!id,
  });
}

/**
 * 根据审批类型获取对应的表单 schema
 */
export function useFormSchemaByType(approvalType: string) {
  return useQuery<FormSchema>({
    queryKey: ['form-schemas', 'by-type', approvalType],
    queryFn: () =>
      aiClient.fetch<FormSchema>(`api/form-schemas/by-type/${approvalType}`),
    enabled: !!approvalType,
    retry: false, // 没有自定义 schema 时返回 404，不重试
  });
}

/**
 * 创建表单 schema
 */
export function useCreateFormSchema() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateFormSchemaPayload) =>
      aiClient.fetch<FormSchema>('api/form-schemas', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['form-schemas'] });
    },
  });
}

/**
 * 更新表单 schema
 */
export function useUpdateFormSchema() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateFormSchemaPayload) =>
      aiClient.fetch<FormSchema>(`api/form-schemas/${payload.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: payload.name,
          approval_type: payload.approval_type,
          fields: payload.fields,
        }),
      }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['form-schemas'] });
      queryClient.invalidateQueries({
        queryKey: ['form-schemas', variables.id],
      });
    },
  });
}

/**
 * 删除表单 schema
 */
export function useDeleteFormSchema() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      aiClient.fetch<void>(`api/form-schemas/${id}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['form-schemas'] });
    },
  });
}

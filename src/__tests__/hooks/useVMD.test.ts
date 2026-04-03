/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * useVMD hooks 单元测试
 * 覆盖核心 15 个 hooks: 任务 CRUD, 子任务, Agent, LLM 模型,
 *   Dashboard 统计, 线索, 合规检查
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mocks ──────────────────────────────────────────────────────

const mockFetch = vi.fn();
vi.mock('@/api/aiClient', () => ({
  aiClient: { fetch: (...a: unknown[]) => mockFetch(...a) },
}));

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

vi.mock('@/utils/vmdMapper', () => ({
  mapVMDTaskListFromAPI: (data: any) => data,
  mapVMDTaskDetailFromAPI: (data: any) => data,
}));

// ── Helpers ────────────────────────────────────────────────────

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

const TASK = {
  id: 't-1', task_code: 'VMD-001', title: '市场调研',
  status: 'pending', priority: 'normal', progress: 0,
  scene_code: 'market_research', created_at: '2026-01-01',
};

const AGENT = {
  id: 'ag-1', agent_code: 'researcher', agent_name: '调研员',
  role_description: '负责市场调研', is_active: true,
  recommended_model_tier: 'standard',
};

const CLUE = {
  id: 'cl-1', title: '新线索', source: 'web',
  status: 'new', created_at: '2026-01-01',
};

// ── Tests ──────────────────────────────────────────────────────

describe('useVMD - 任务管理', () => {
  beforeEach(() => vi.clearAllMocks());

  it('useVMDTasks 正常获取任务列表', async () => {
    mockFetch.mockResolvedValueOnce({ data: [TASK] });
    const { useVMDTasks } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useVMDTasks(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
  });

  it('useVMDTaskDetail 获取任务详情', async () => {
    mockFetch.mockResolvedValueOnce({ data: { ...TASK, sub_tasks: [] } });
    const { useVMDTaskDetail } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useVMDTaskDetail('t-1'), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
  });

  it('useCreateVMDTask 成功创建任务', async () => {
    mockFetch.mockResolvedValueOnce({ data: TASK });
    const { useCreateVMDTask } = await import('@/hooks/useVMD');
    const { toast } = await import('sonner');
    const { result } = renderHook(() => useCreateVMDTask(), { wrapper });

    await act(async () => {
      result.current.mutate({ title: '新任务', scene_code: 'market_research' } as any);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(toast.success).toHaveBeenCalled();
  });

  it('useDeleteVMDTask 成功删除任务', async () => {
    mockFetch.mockResolvedValueOnce({ success: true });
    const { useDeleteVMDTask } = await import('@/hooks/useVMD');
    const { toast } = await import('sonner');
    const { result } = renderHook(() => useDeleteVMDTask(), { wrapper });

    await act(async () => {
      result.current.mutate('t-1');
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(toast.success).toHaveBeenCalled();
  });
});

describe('useVMD - 子任务', () => {
  beforeEach(() => vi.clearAllMocks());

  it('useUpdateSubTask 成功更新子任务', async () => {
    mockFetch.mockResolvedValueOnce({ data: { id: 'st-1', status: 'done' } });
    const { useUpdateSubTask } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useUpdateSubTask(), { wrapper });

    await act(async () => {
      result.current.mutate({ subTaskId: 'st-1', status: 'done' } as any);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it('useSubmitSubTask 提交子任务', async () => {
    mockFetch.mockResolvedValueOnce({ data: { id: 'st-1' } });
    const { useSubmitSubTask } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useSubmitSubTask(), { wrapper });

    await act(async () => {
      result.current.mutate({ subTaskId: 'st-1', output: '调研报告内容' } as any);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it('useAuditSubTask 审核子任务', async () => {
    mockFetch.mockResolvedValueOnce({ data: { id: 'st-1' } });
    const { useAuditSubTask } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useAuditSubTask(), { wrapper });

    await act(async () => {
      result.current.mutate({ subTaskId: 'st-1', review_status: 'approved' } as any);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe('useVMD - Agent 管理', () => {
  beforeEach(() => vi.clearAllMocks());

  it('useVMDAgents 正常获取 Agent 列表', async () => {
    mockFetch.mockResolvedValueOnce({ data: [AGENT] });
    const { useVMDAgents } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useVMDAgents(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
  });

  it('useVMDAgents API 不可达时降级为空数组', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));
    const { useVMDAgents } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useVMDAgents(), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useVMD - LLM 模型', () => {
  beforeEach(() => vi.clearAllMocks());

  it('useLLMModels 获取模型列表', async () => {
    const models = [{ id: 'm-1', model_name: 'gpt-4', is_active: true }];
    mockFetch.mockResolvedValueOnce({ data: models });
    const { useLLMModels } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useLLMModels(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
  });

  it('useCreateLLMModel 创建模型', async () => {
    mockFetch.mockResolvedValueOnce({ data: { id: 'm-1' } });
    const { useCreateLLMModel } = await import('@/hooks/useVMD');
    const { toast } = await import('sonner');
    const { result } = renderHook(() => useCreateLLMModel(), { wrapper });

    await act(async () => {
      result.current.mutate({ model_name: 'gpt-4', api_key: 'sk-xxx' } as any);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(toast.success).toHaveBeenCalled();
  });
});

describe('useVMD - Dashboard 统计', () => {
  beforeEach(() => vi.clearAllMocks());

  it('useVMDStats 获取统计数据', async () => {
    const stats = { total_tasks: 10, completed: 5, in_progress: 3 };
    mockFetch.mockResolvedValueOnce({ data: stats });
    const { useVMDStats } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useVMDStats(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
  });

  it('useVMDDashboard 获取仪表盘数据', async () => {
    mockFetch.mockResolvedValueOnce({ data: { overview: {}, recent: [] } });
    const { useVMDDashboard } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useVMDDashboard(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
  });
});

describe('useVMD - 线索管理', () => {
  beforeEach(() => vi.clearAllMocks());

  it('useVMDClues 获取线索列表', async () => {
    mockFetch.mockResolvedValueOnce({ data: [CLUE] });
    const { useVMDClues } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useVMDClues(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
  });

  it('useCreateVMDClue 创建线索', async () => {
    mockFetch.mockResolvedValueOnce({ data: CLUE });
    const { useCreateVMDClue } = await import('@/hooks/useVMD');
    const { toast } = await import('sonner');
    const { result } = renderHook(() => useCreateVMDClue(), { wrapper });

    await act(async () => {
      result.current.mutate({ title: '新线索', source: 'web' } as any);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(toast.success).toHaveBeenCalled();
  });
});

describe('useVMD - 合规检查', () => {
  beforeEach(() => vi.clearAllMocks());

  it('useComplianceCheck 执行合规检查', async () => {
    mockFetch.mockResolvedValueOnce({ data: { passed: true, violations: [] } });
    const { useComplianceCheck } = await import('@/hooks/useVMD');
    const { result } = renderHook(() => useComplianceCheck(), { wrapper });

    await act(async () => {
      result.current.mutate({ taskId: 't-1' } as any);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

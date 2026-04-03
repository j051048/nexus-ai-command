/* eslint-disable @typescript-eslint/no-explicit-any */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ReactFlowProvider } from '@xyflow/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import WorkflowDesigner from '@/pages/WorkflowDesigner';
import { describe, it, expect, vi } from 'vitest';
import '@testing-library/jest-dom';
import React from 'react';

// Mock useWorkflows hooks
vi.mock('@/hooks/useWorkflows', () => ({
  useWorkflows: () => ({ data: [], isLoading: false }),
  useWorkflow: () => ({ data: null, isLoading: false }),
  useCreateWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useToggleWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetDefaultWorkflow: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useApprovalTypes: () => ({ data: [], isLoading: false }),
}));

// Mock sonner
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

// Mock supabase
vi.mock('@/integrations/supabase/client', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'test' } },
      }),
    },
  },
}));

// Mock useIsMobile
vi.mock('@/hooks/use-mobile', () => ({
  useIsMobile: () => false,
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/workflows/new']}>
        <ReactFlowProvider>
          {children}
        </ReactFlowProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('WorkflowDesigner Persistence & Visual Logic', () => {
  it('正确渲染设计器页面', () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <WorkflowDesigner />
      </Wrapper>
    );

    // 验证页面基本元素渲染
    expect(screen.getByText(/保存/i)).toBeInTheDocument();
  });

  it('新建流程时显示默认名称', () => {
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <WorkflowDesigner />
      </Wrapper>
    );

    // 新建流程默认名称显示在页面上
    expect(screen.getByText('新建流程')).toBeInTheDocument();
  });
});

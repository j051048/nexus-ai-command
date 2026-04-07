import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { forwardRef, useImperativeHandle } from 'react';
import { WorkflowDesigner } from '@/pages/WorkflowDesigner';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Ultra-stable mocks
const mocks = vi.hoisted(() => ({
  useWorkflow: vi.fn(() => ({ data: null, isLoading: false })),
  useIsMobile: vi.fn(() => false),
}));

vi.mock('@/hooks/useWorkflows', () => ({
  useWorkflow: mocks.useWorkflow,
  useCreateWorkflow: vi.fn(() => ({ isPending: false })),
  useUpdateWorkflow: vi.fn(() => ({ isPending: false })),
}));

vi.mock('@/hooks/use-mobile', () => ({
  useIsMobile: mocks.useIsMobile,
}));

vi.mock('@/components/workflow/WorkflowCanvas', () => ({
  WorkflowCanvas: forwardRef((props, ref) => {
    useImperativeHandle(ref, () => ({
      getWorkflowData: vi.fn(() => ({ steps: [], conditions: [] })),
      loadWorkflowData: vi.fn(),
    }));
    return <div data-testid="mock-canvas" />;
  }),
}));
vi.mock('@/components/workflow/WorkflowSidebar', () => ({
  WorkflowSidebar: () => <div data-testid="mock-sidebar" />,
}));
vi.mock('@/components/workflow/WorkflowProperties', () => ({
  WorkflowProperties: () => <div data-testid="mock-properties" />,
}));
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } }
});

describe('WorkflowDesigner Core Interactions', () => {
  it('should toggle name editing and update name', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <WorkflowDesigner />
        </MemoryRouter>
      </QueryClientProvider>
    );

    const name = screen.getByText('新建流程');
    fireEvent.click(name);
    
    // Find input by display value instead of role
    const input = screen.getByDisplayValue('新建流程');
    fireEvent.change(input, { target: { value: 'Updated Workflow' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
    
    expect(screen.getByText('Updated Workflow')).toBeDefined();
  });

  it('should show mobile warning when isMobile is true', () => {
    mocks.useIsMobile.mockReturnValue(true);
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <WorkflowDesigner />
        </MemoryRouter>
      </QueryClientProvider>
    );
    
    expect(screen.getByText('流程设计器')).toBeDefined();
    expect(screen.getByText(/需要在桌面端操作/)).toBeDefined();
  });
});

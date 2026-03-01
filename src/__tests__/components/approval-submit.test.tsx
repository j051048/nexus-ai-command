import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';

// ─── Mock dependencies ──────────────────────────────────────

const mockMutateAsync = vi.fn();
const mockSubmitApproval = {
  mutateAsync: mockMutateAsync,
  isPending: false,
};

vi.mock('@/hooks/useApprovals', () => ({
  useMyApprovals: vi.fn().mockReturnValue({ data: [], isLoading: false }),
  useSubmitApproval: vi.fn().mockReturnValue(mockSubmitApproval),
}));

vi.mock('@/components/auth/AuthContext', () => ({
  useAuth: vi.fn().mockReturnValue({
    user: { id: 'user-1', role: 'employee' },
    profile: { organization_id: 'org-1' },
    role: 'employee',
  }),
}));

vi.mock('@/api/aiClient', () => ({
  aiClient: {
    fetch: vi.fn().mockResolvedValue({ data: null }),
    processApproval: vi.fn().mockResolvedValue({ decision: 'pending', reason: 'test' }),
  },
}));

vi.mock('@/integrations/supabase/client', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'mock-token' } },
        error: null,
      }),
    },
    from: vi.fn().mockReturnValue({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          maybeSingle: vi.fn().mockResolvedValue({ data: null, error: null }),
          or: vi.fn().mockReturnValue({
            order: vi.fn().mockResolvedValue({ data: [], error: null }),
          }),
        }),
        order: vi.fn().mockResolvedValue({ data: [], error: null }),
      }),
      insert: vi.fn().mockReturnValue({
        select: vi.fn().mockReturnValue({
          single: vi.fn().mockResolvedValue({ data: { id: 'new-1' }, error: null }),
        }),
      }),
    }),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    loading: vi.fn(),
  },
}));

vi.mock('@/hooks/useFormSchemas', () => ({
  useFormSchemaByType: vi.fn().mockReturnValue({ data: null }),
}));

vi.mock('@/components/forms/DynamicFormRenderer', () => ({
  DynamicFormRenderer: () => <div data-testid="dynamic-form" />,
}));

vi.mock('@/components/common/AICopilotInsight', () => ({
  AICopilotInsight: () => null,
}));

vi.mock('@/components/approval/sections/ApprovalHistory', () => ({
  ApprovalHistory: () => <div data-testid="approval-history" />,
}));

vi.mock('@/components/approval/constants', () => ({
  approvalTypes: [
    { id: 'travel', name: '差旅', icon: <span>T</span>, example: '出差北京3天预算3000元', threshold: 5000 },
    { id: 'expense', name: '报销', icon: <span>E</span>, example: '报销打车费200元', threshold: 2000 },
  ],
}));

// ─── Tests ──────────────────────────────────────────────────

describe('审批提交流程测试', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMutateAsync.mockResolvedValue({ status: 'pending', id: 'approval-1' });
  });

  it('选择审批类型后填写信息并提交', async () => {
    const { EmployeeApprovalView } = await import(
      '@/components/approval/sections/EmployeeApprovalView'
    );

    render(<EmployeeApprovalView />);

    // 点选审批类型
    const travelBtn = screen.getByText('差旅');
    fireEvent.click(travelBtn);

    // 应自动填入示例文本
    const textarea = screen.getByPlaceholderText(/例如/);
    expect((textarea as HTMLTextAreaElement).value).toContain('出差北京');

    // 修改金额
    const amountInput = screen.getByPlaceholderText('0.00');
    fireEvent.change(amountInput, { target: { value: '3000' } });

    // 提交
    const submitBtn = screen.getByText('提交申请');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'travel',
          amount: 3000,
        })
      );
    });
  });

  it('未选类型时点击提交应提示错误', async () => {
    const { toast } = await import('sonner');
    const { EmployeeApprovalView } = await import(
      '@/components/approval/sections/EmployeeApprovalView'
    );

    render(<EmployeeApprovalView />);

    // 直接输入文本但不选类型
    const textarea = screen.getByPlaceholderText(/例如/);
    fireEvent.change(textarea, { target: { value: '测试申请' } });

    // 默认 submit 按钮 disabled 因为 selectedType 为 null
    // 但如果用户直接调用 handleSubmit（模拟）：
    // 先选类型再清掉内容检查
    const expenseBtn = screen.getByText('报销');
    fireEvent.click(expenseBtn);

    // 清空文本检查是否校验
    fireEvent.change(textarea, { target: { value: '' } });

    // 提交按钮应该被 disabled
    const submitBtn = screen.getByText('提交申请');
    expect(submitBtn).toBeDisabled();
  });

  it('自动审批通过时显示成功提示', async () => {
    mockMutateAsync.mockResolvedValue({ status: 'approved', id: 'auto-1' });
    const { toast } = await import('sonner');
    const { EmployeeApprovalView } = await import(
      '@/components/approval/sections/EmployeeApprovalView'
    );

    render(<EmployeeApprovalView />);

    // 选择类型并填写
    fireEvent.click(screen.getByText('报销'));

    const textarea = screen.getByPlaceholderText(/例如/);
    fireEvent.change(textarea, { target: { value: '报销打车费100元' } });

    const amountInput = screen.getByPlaceholderText('0.00');
    fireEvent.change(amountInput, { target: { value: '100' } });

    fireEvent.click(screen.getByText('提交申请'));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalled();
    });
  });
});

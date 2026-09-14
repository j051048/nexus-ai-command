import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AutoApprovalRules } from '@/components/approval/AutoApprovalRules';

const mocks = vi.hoisted(() => ({
  auth: {
    user: { id: 'user-a' }, profile: { user_id: 'user-a', organization_id: 'org-a' },
    role: 'boss', isSuperAdmin: false, loading: false,
  },
  get: vi.fn(), post: vi.fn(), delete: vi.fn(),
}));
vi.mock('@/components/auth/AuthContext', () => ({ useAuth: () => mocks.auth }));
vi.mock('@/api/aiClient', () => ({ aiClient: mocks }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const rule = { id: 'rule-a', name: 'Small expense', approval_type: 'expense', condition_field: 'amount', condition_op: 'lte', condition_value: 100, is_active: true };
let client: QueryClient;
function View() { return <QueryClientProvider client={client}><AutoApprovalRules /></QueryClientProvider>; }
beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  mocks.auth.role = 'boss';
  mocks.auth.profile.organization_id = 'org-a';
  mocks.get.mockReset().mockResolvedValue({ data: { success: true, data: [rule] } });
  mocks.post.mockReset().mockResolvedValue({ data: { success: true } });
  mocks.delete.mockReset().mockResolvedValue({ data: { success: true } });
});
afterEach(() => { cleanup(); client.clear(); });

describe('automatic approval rule controls', () => {
  it('uses the authenticated role and callable client methods to list and delete', async () => {
    render(<View />);
    await screen.findByText(rule.name);
    fireEvent.click(screen.getByRole('button', { name: `删除规则 ${rule.name}` }));
    await waitFor(() => expect(mocks.delete).toHaveBeenCalledWith('/api/approval/auto-rules/rule-a', expect.objectContaining({ headers: { 'X-Org-ID': 'org-a' } })));
    expect(mocks.get.mock.calls[0][1].headers).toEqual({ 'X-Org-ID': 'org-a' });
  });

  it('creates a rule with a numeric threshold and the current tenant', async () => {
    render(<View />);
    fireEvent.click(await screen.findByRole('button', { name: '新增规则' }));
    fireEvent.change(screen.getByPlaceholderText('如：小额报销自动通过'), { target: { value: 'Expense limit' } });
    fireEvent.change(screen.getByPlaceholderText('500'), { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: '创建规则' }));
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith('/api/approval/auto-rules', {
      name: 'Expense limit', approval_type: 'expense', condition_field: 'amount', condition_op: 'lte', condition_value: 500,
    }, expect.objectContaining({ headers: { 'X-Org-ID': 'org-a' } })));
  });

  it('does not mount controls or load rules for a regular employee', () => {
    mocks.auth.role = 'employee';
    render(<View />);
    expect(screen.queryByText('自动审批规则')).not.toBeInTheDocument();
    expect(mocks.get).not.toHaveBeenCalled();
  });

  it('shows a retry state rather than a false empty list on failure', async () => {
    mocks.get.mockRejectedValueOnce(new Error('unavailable'));
    render(<View />);
    expect(await screen.findByRole('alert')).toHaveTextContent('规则加载失败');
    expect(screen.queryByText('暂无自动审批规则')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await screen.findByText(rule.name);
  });

  it('closes an unsaved rule dialog when switching enterprise', async () => {
    const { rerender } = render(<View />);
    fireEvent.click(await screen.findByRole('button', { name: '新增规则' }));
    fireEvent.change(screen.getByPlaceholderText('如：小额报销自动通过'), { target: { value: 'Private A draft' } });
    mocks.auth.profile.organization_id = 'org-b';
    mocks.get.mockResolvedValue({ data: { success: true, data: [] } });
    rerender(<View />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await screen.findByText('暂无自动审批规则');
    expect(screen.queryByText(rule.name)).not.toBeInTheDocument();
    expect(mocks.post).not.toHaveBeenCalled();
  });
});

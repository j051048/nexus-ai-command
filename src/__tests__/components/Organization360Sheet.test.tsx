import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Organization360Sheet } from '@/components/super-admin/Organization360Sheet';

const mutateAsync = vi.fn();

vi.mock('@/hooks/useSuperAdminConsole', () => ({
  useAdminOrganization360: () => ({
    isLoading: false,
    data: {
      id: 'org-1',
      name: '精密仪器公司',
      slug: 'precision-instruments',
      status: 'active',
      plan: 'professional',
      access_state: 'active',
      created_at: '2026-01-01T00:00:00Z',
      user_count: 2,
      active_users_30d: 2,
      usage_30d: { requests: 12, tokens: 2400, cost_usd: 0.42 },
      subscription: {
        org_id: 'org-1',
        plan: 'professional',
        status: 'active',
        current_period_end: null,
      },
      quotas: {
        monthly_token_limit: 100000,
        monthly_api_call_limit: 10000,
        storage_limit_mb: 1024,
      },
      users: [
        {
          id: 'user-1',
          email: 'owner@example.com',
          full_name: '负责人',
          role: 'boss',
          status: 'active',
          last_active_at: '2026-07-18T00:00:00Z',
        },
      ],
      access_requests: [],
      access_versions: [],
      commercial_records: [],
      audit_timeline: [],
    },
  }),
  useAdjustOrganizationAccess: () => ({ mutateAsync, isPending: false }),
  useSetOrganizationAccess: () => ({ mutateAsync, isPending: false }),
  useUpdateOrganizationQuotas: () => ({ mutateAsync, isPending: false }),
  useAccessChangeAction: () => ({ mutateAsync, isPending: false }),
  useUpsertCommercialRecord: () => ({ mutateAsync, isPending: false }),
}));

describe('Organization360Sheet', () => {
  it('保持拆分前的会员、商业、用户和审计视图入口', () => {
    render(
      <Organization360Sheet
        organization={{
          id: 'org-1',
          name: '精密仪器公司',
          slug: 'precision-instruments',
          status: 'active',
          plan: 'professional',
          access_state: 'active',
          created_at: '2026-01-01T00:00:00Z',
        }}
        onOpenChange={vi.fn()}
        can={() => true}
      />
    );

    expect(screen.getByText('精密仪器公司')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '会员设置' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '商业记录' })).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByRole('tab', { name: '商业记录' }), {
      button: 0,
      ctrlKey: false,
    });
    expect(screen.getByText('合同、回款与发票')).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByRole('tab', { name: '用户' }), {
      button: 0,
      ctrlKey: false,
    });
    expect(screen.getByText('owner@example.com')).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByRole('tab', { name: '操作记录' }), {
      button: 0,
      ctrlKey: false,
    });
    expect(screen.getByText('操作时间线')).toBeInTheDocument();
  });
});

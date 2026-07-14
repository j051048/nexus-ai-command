import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AccessRequestQueue } from '@/components/super-admin/AccessRequestQueue';
import { AdminAnalyticsPanel } from '@/components/super-admin/AdminAnalyticsPanel';
import { AdminExceptionsPanel } from '@/components/super-admin/AdminExceptionsPanel';

const mutateAsync = vi.fn();

vi.mock('@/hooks/useSuperAdminConsole', () => ({
  useDecideSubscriptionRequest: () => ({ mutateAsync, isPending: false }),
  useBatchDecideSubscriptionRequests: () => ({ mutateAsync, isPending: false }),
  useOperationalExceptions: () => ({
    data: [
      {
        id: 'expiring:org-1',
        org_id: 'org-1',
        organization_name: '精密仪器公司',
        severity: 'high',
        title: '会员即将到期',
        detail: '将在 7 天内到期。',
        recommended_action: '联系客户确认续期',
      },
    ],
    isLoading: false,
  }),
  useOperationalAnalytics: () => ({
    data: {
      plan_distribution: { professional: 3, enterprise: 1 },
      expiring: { '7_days': 1, '30_days': 2, '90_days': 3 },
      requests_30d: { approved: 5, rejected: 1 },
      average_review_hours: 2.5,
      commercial: { collected_cents: 100000, outstanding_cents: 20000, overdue_orders: 1 },
      top_cost_organizations: [],
    },
    isLoading: false,
  }),
}));

describe('super-admin operating views', () => {
  beforeEach(() => mutateAsync.mockReset());

  it('surfaces actionable operational exceptions', () => {
    const onOpenOrganization = vi.fn();
    render(<AdminExceptionsPanel onOpenOrganization={onOpenOrganization} />);

    expect(screen.getByText('会员即将到期')).toBeInTheDocument();
    expect(screen.getByText('建议：联系客户确认续期')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '处理' }));
    expect(onOpenOrganization).toHaveBeenCalledWith('org-1');
  });

  it('renders decision-oriented operational analytics', () => {
    render(<AdminAnalyticsPanel />);

    expect(screen.getByText('2.5 小时')).toBeInTheDocument();
    expect(screen.getByText('¥200')).toBeInTheDocument();
    expect(screen.getByText('未来 7 天')).toBeInTheDocument();
  });

  it('shows request SLA and supports queue selection', () => {
    render(
      <AccessRequestQueue
        loading={false}
        requests={[
          {
            id: 'request-1',
            org_id: 'org-1',
            requested_plan: 'professional',
            requested_days: 365,
            status: 'pending',
            created_at: new Date().toISOString(),
            organization: { id: 'org-1', name: '精密仪器公司', slug: 'instrument' },
            priority: 'urgent',
            waiting_seconds: 90000,
            is_overdue: true,
          },
        ]}
      />,
    );

    expect(screen.getByText('等待 1 天')).toBeInTheDocument();
    expect(screen.getAllByText('紧急')).toHaveLength(2);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByText('已选 1 项')).toBeInTheDocument();
  });

  it('keeps approval controls hidden for read-only administrators', () => {
    render(
      <AccessRequestQueue
        loading={false}
        canManage={false}
        requests={[
          {
            id: 'request-2',
            org_id: 'org-2',
            requested_plan: 'professional',
            requested_days: 365,
            status: 'pending',
            created_at: new Date().toISOString(),
            organization: { id: 'org-2', name: '只读企业', slug: 'readonly' },
          },
        ]}
      />,
    );

    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '批准' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '拒绝' })).not.toBeInTheDocument();
  });
});

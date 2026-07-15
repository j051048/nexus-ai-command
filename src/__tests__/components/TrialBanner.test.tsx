import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TrialBanner } from '@/components/billing/TrialBanner';

const useSubscriptionMock = vi.fn();

vi.mock('@/hooks/useBilling', () => ({
  useSubscription: () => useSubscriptionMock(),
}));

function renderBanner() {
  return render(
    <MemoryRouter>
      <TrialBanner />
    </MemoryRouter>
  );
}

describe('TrialBanner', () => {
  beforeEach(() => {
    localStorage.clear();
    useSubscriptionMock.mockReset();
  });

  it('does not show marketing prompts for admin-approved access', () => {
    useSubscriptionMock.mockReturnValue({
      data: {
        org_id: 'org-1',
        plan: 'professional',
        status: 'active',
        current_period_end: '2099-12-31T23:59:59Z',
        access_source: 'admin_approved',
        has_paid_access: true,
        is_expired: false,
        notice_policy: 'none',
      },
      isLoading: false,
      isError: false,
    });

    renderBanner();

    expect(screen.queryByText(/体验|付费|升级|会员状态/)).not.toBeInTheDocument();
  });

  it('stays quiet when subscription data is missing or unconfigured', () => {
    useSubscriptionMock.mockReturnValue({
      data: null,
      isLoading: false,
      isError: false,
    });

    renderBanner();

    expect(document.body.textContent).toBe('');
  });

  it('shows an organization-wide activation notice for non-members', () => {
    useSubscriptionMock.mockReturnValue({
      data: {
        org_id: 'org-1',
        plan: 'free',
        status: 'unconfigured',
        current_period_end: null,
        access_source: 'default',
        has_paid_access: false,
        is_expired: false,
        notice_policy: 'action_required',
      },
      isLoading: false,
      isError: false,
    });

    renderBanner();

    expect(screen.getByText('企业会员尚未开通')).toBeVisible();
    expect(screen.getByRole('button', { name: '申请开通' })).toBeVisible();
  });

  it('shows a compact action notice only after access expires', () => {
    useSubscriptionMock.mockReturnValue({
      data: {
        org_id: 'org-1',
        plan: 'professional',
        status: 'expired',
        current_period_end: '2020-01-01T00:00:00Z',
        access_source: 'admin_approved',
        has_paid_access: false,
        is_expired: true,
        notice_policy: 'action_required',
      },
      isLoading: false,
      isError: false,
    });

    renderBanner();

    expect(screen.getByText('企业会员已到期')).toBeVisible();
    expect(screen.getByRole('button', { name: '查看状态' })).toBeVisible();
  });
});

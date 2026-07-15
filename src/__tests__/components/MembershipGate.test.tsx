import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MembershipGate } from '@/components/billing/MembershipGate';

const useSubscriptionMock = vi.fn();

vi.mock('@/hooks/useBilling', () => ({
  useSubscription: () => useSubscriptionMock(),
}));

function renderGate() {
  return render(
    <MemoryRouter>
      <MembershipGate>
        <div>完整业务功能</div>
      </MembershipGate>
    </MemoryRouter>
  );
}

describe('MembershipGate', () => {
  beforeEach(() => {
    useSubscriptionMock.mockReset();
  });

  it('allows every user in a member organization to use the feature', () => {
    useSubscriptionMock.mockReturnValue({
      data: { has_paid_access: true },
      isLoading: false,
      isError: false,
    });

    renderGate();

    expect(screen.getByText('完整业务功能')).toBeInTheDocument();
    expect(screen.queryByText('该功能需要企业会员')).not.toBeInTheDocument();
  });

  it('limits advanced features for nonmember organizations', () => {
    useSubscriptionMock.mockReturnValue({
      data: { has_paid_access: false },
      isLoading: false,
      isError: false,
    });

    renderGate();

    expect(screen.getByText('该功能需要企业会员')).toBeInTheDocument();
    expect(screen.queryByText('完整业务功能')).not.toBeInTheDocument();
  });

  it('fails open during a temporary billing-service outage', () => {
    useSubscriptionMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    renderGate();

    expect(screen.getByText('完整业务功能')).toBeInTheDocument();
  });
});

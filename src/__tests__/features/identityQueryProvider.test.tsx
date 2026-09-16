import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { IdentityQueryProvider } from '@/components/auth/IdentityQueryProvider';

const state = vi.hoisted(() => ({ user: { id: 'a' }, profile: { organization_id: 'org-a' }, role: 'employee', isSuperAdmin: false }));
vi.mock('@/components/auth/AuthContext', () => ({ useAuth: () => state }));
afterEach(cleanup);

it('isolates identical query keys and aborts old requests when identity changes', async () => {
  let oldSignal: AbortSignal | undefined;
  let completeOld: ((value: string) => void) | undefined;
  function Probe() {
    const { data } = useQuery({
      queryKey: ['private-records'],
      queryFn: ({ signal }) => {
        if (state.user.id === 'a') {
          oldSignal = signal;
          return new Promise<string>(resolve => { completeOld = resolve; });
        }
        return Promise.resolve('B tenant records');
      },
    });
    return <p>{data || 'loading'}</p>;
  }
  const view = render(<IdentityQueryProvider><Probe /></IdentityQueryProvider>);
  await waitFor(() => expect(oldSignal).toBeDefined());
  state.user = { id: 'b' }; state.profile = { organization_id: 'org-b' };
  view.rerender(<IdentityQueryProvider><Probe /></IdentityQueryProvider>);
  expect(await screen.findByText('B tenant records')).toBeInTheDocument();
  expect(oldSignal?.aborted).toBe(true);
  completeOld?.('A confidential records');
  await waitFor(() => expect(screen.queryByText('A confidential records')).not.toBeInTheDocument());
});

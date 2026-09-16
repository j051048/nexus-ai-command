import { useEffect, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { toast } from 'sonner';

import { useAuth } from './AuthContext';

function ScopedQueryClient({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: { staleTime: 5 * 60 * 1000, retry: 2, refetchOnWindowFocus: false },
      mutations: {
        onError: error => toast.error(error instanceof Error ? error.message : '操作失败，请重试'),
      },
    },
  }));
  useEffect(() => () => {
    void client.cancelQueries();
    client.clear();
  }, [client]);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

export function IdentityQueryProvider({ children }: { children: ReactNode }) {
  const { user, profile, role, isSuperAdmin } = useAuth();
  const identity = JSON.stringify([user?.id, profile?.organization_id, role, isSuperAdmin]);
  // Remount local business state too. Old mutations retain only the old query client.
  return <ScopedQueryClient key={identity}>{children}</ScopedQueryClient>;
}

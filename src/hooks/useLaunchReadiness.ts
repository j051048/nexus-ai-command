import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { httpClient } from '@/lib/httpClient';

export interface LaunchReadiness {
  organization_id: string;
  user_id: string;
  uploaded: boolean;
  searchable: boolean;
  facts_confirmed: boolean;
  artifact_ready: boolean;
  artifact_id: string | null;
}

export function useLaunchReadiness() {
  const { profile, user } = useAuth();
  const orgId = profile?.organization_id;
  const userId = user?.id;
  return useQuery({
    queryKey: ['launch-readiness', orgId, userId],
    enabled: Boolean(orgId && userId),
    staleTime: 15_000,
    refetchInterval: 30_000,
    retry: 1,
    queryFn: async ({ signal }) => {
      const response = await httpClient.get('/api/onboarding/readiness', {
        signal, headers: { 'X-Silent-Error': '1', 'X-Org-ID': orgId },
      });
      const value: LaunchReadiness = response.data.data;
      if (value.organization_id !== orgId || value.user_id !== userId) {
        throw new Error('Readiness identity mismatch');
      }
      return value;
    },
  });
}

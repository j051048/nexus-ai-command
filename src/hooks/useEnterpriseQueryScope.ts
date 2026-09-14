import { useAuth } from '@/components/auth/AuthContext';

/** Bind cached data and requests to the same resolved identity, never localStorage. */
export function useEnterpriseQueryScope() {
  const { user, profile, role, isSuperAdmin, loading } = useAuth();
  const orgId = profile?.organization_id;
  const userId = user?.id;
  const enabled = Boolean(!loading && orgId && userId && profile?.user_id === userId);

  return {
    enabled,
    key: [orgId, userId, role, Boolean(isSuperAdmin), enabled] as const,
    options(signal?: AbortSignal) {
      if (!enabled || !orgId) throw new Error('企业身份尚未就绪，请稍后重试');
      return { signal, headers: { 'X-Org-ID': orgId } };
    },
  };
}

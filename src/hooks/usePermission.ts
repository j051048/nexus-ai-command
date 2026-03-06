import { useState, useCallback, useEffect, useMemo } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useUser } from '@/contexts/UserContext';

interface PermissionCheck {
  resource: string;
  action: string;
  allowed: boolean;
  loading: boolean;
}

const permissionCache = new Map<string, { allowed: boolean; expires: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * P1-6: Frontend permission hook that calls backend ABAC policy engine.
 * Replaces hardcoded role checks with centralized permission evaluation.
 */
export function usePermission(resource: string, action: string): PermissionCheck {
  const { user } = useUser();
  const [allowed, setAllowed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.id) {
      setAllowed(false);
      setLoading(false);
      return;
    }

    const cacheKey = `${user.id}:${resource}:${action}`;
    const cached = permissionCache.get(cacheKey);
    if (cached && cached.expires > Date.now()) {
      setAllowed(cached.allowed);
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function checkPermission() {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        const token = session?.access_token;
        if (!token) {
          setAllowed(false);
          return;
        }

        const baseUrl = import.meta.env.VITE_API_BASE_URL || (
          window.location.hostname === 'localhost' ? 'http://localhost:8000' : window.location.origin
        );
        const url = `${baseUrl.replace(/\/$/, '')}/api/permissions/check`;

        const resp = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ resource, action }),
        });

        if (!cancelled) {
          if (resp.ok) {
            const data = await resp.json();
            const isAllowed = data.allowed ?? false;
            setAllowed(isAllowed);
            permissionCache.set(cacheKey, { allowed: isAllowed, expires: Date.now() + CACHE_TTL });
          } else {
            // Fallback: allow based on frontend role for backwards compatibility
            setAllowed(fallbackRoleCheck(user.role, resource, action));
          }
        }
      } catch {
        // Network error: fallback to local role check
        if (!cancelled) {
          setAllowed(fallbackRoleCheck(user.role, resource, action));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    checkPermission();
    return () => { cancelled = true; };
  }, [user?.id, user?.role, resource, action]);

  return { resource, action, allowed, loading };
}

/**
 * Batch permission check for multiple resource/action pairs.
 */
export function usePermissions(checks: { resource: string; action: string }[]) {
  const { user } = useUser();
  const [results, setResults] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  const checksStr = useMemo(() => JSON.stringify(checks), [checks]);

  useEffect(() => {
    if (!user?.id || checks.length === 0) {
      setLoading(false);
      return;
    }

    // Use cache where possible
    const needsCheck: typeof checks = [];
    const cached: Record<string, boolean> = {};

    for (const c of checks) {
      const key = `${user.id}:${c.resource}:${c.action}`;
      const entry = permissionCache.get(key);
      if (entry && entry.expires > Date.now()) {
        cached[`${c.resource}:${c.action}`] = entry.allowed;
      } else {
        needsCheck.push(c);
      }
    }

    if (needsCheck.length === 0) {
      setResults(cached);
      setLoading(false);
      return;
    }

    // For uncached: fallback to role-based check (batch API not yet available)
    const fallbackResults = { ...cached };
    for (const c of needsCheck) {
      fallbackResults[`${c.resource}:${c.action}`] = fallbackRoleCheck(user.role, c.resource, c.action);
    }
    setResults(fallbackResults);
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, user?.role, checksStr]);

  const can = useCallback((resource: string, action: string) => {
    return results[`${resource}:${action}`] ?? false;
  }, [results]);

  return { can, loading };
}

/**
 * Fallback role-based check when backend is unavailable.
 */
function fallbackRoleCheck(role: string, resource: string, action: string): boolean {
  // Boss/admin can do everything
  if (role === 'boss' || role === 'admin') return true;

  // Manager: read + write on most resources, no system admin
  if (role === 'manager') {
    if (resource === 'system' || resource === 'billing') return false;
    return true;
  }

  // Employee: read-only on team resources, full access on own
  if (role === 'employee') {
    if (action === 'read') return true;
    if (resource === 'own_profile' || resource === 'own_tasks') return true;
    if (action === 'delete' || action === 'admin') return false;
    return resource === 'chat' || resource === 'documents';
  }

  return false;
}

/**
 * Invalidate permission cache (call after role change or plan upgrade).
 */
export function invalidatePermissionCache() {
  permissionCache.clear();
}

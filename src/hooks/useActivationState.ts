import { useCallback, useEffect, useMemo, useState } from 'react';

import { useAuth } from '@/components/auth/AuthContext';
import {
  ACTIVATION_OPEN_EVENT,
  ACTIVATION_UPDATED_EVENT,
  type ActivationState,
  isActivationComplete,
  mergeActivationState,
  readActivationState,
} from '@/features/activation/activationState';

export function useActivationState() {
  const { profile, user } = useAuth();
  const scope = useMemo(
    () => profile?.organization_id || user?.id || 'workspace',
    [profile?.organization_id, user?.id],
  );
  const [state, setState] = useState<ActivationState>(() => readActivationState(scope));

  useEffect(() => {
    setState(readActivationState(scope));
  }, [scope]);

  useEffect(() => {
    const sync = (event: Event) => {
      const detail = (event as CustomEvent<{ scope?: string }>).detail;
      if (!detail?.scope || detail.scope === scope) setState(readActivationState(scope));
    };
    window.addEventListener(ACTIVATION_UPDATED_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(ACTIVATION_UPDATED_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, [scope]);

  const update = useCallback((patch: Partial<ActivationState>) => {
    setState((current) => mergeActivationState(scope, current, patch));
  }, [scope]);

  const open = useCallback(() => {
    window.dispatchEvent(new CustomEvent(ACTIVATION_OPEN_EVENT));
  }, []);

  return {
    scope,
    state,
    update,
    open,
    isComplete: isActivationComplete(state),
  };
}

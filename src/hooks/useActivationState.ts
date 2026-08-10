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
import { httpClient } from '@/lib/httpClient';

interface ServerActivationState {
  step?: ActivationState['step'];
  company_name?: string;
  instrument_families?: ActivationState['instrumentFamilies'];
  markets?: string;
  uploaded_document_count?: number;
  uploaded_file_names?: string[];
  facts_confirmed?: boolean;
  first_outcome?: ActivationState['firstOutcome'];
  completed_at?: string;
  dismissed_until?: string;
}

function fromServer(value: ServerActivationState): Partial<ActivationState> {
  const mapped: Partial<ActivationState> = {
    step: value.step,
    companyName: value.company_name,
    instrumentFamilies: value.instrument_families,
    markets: value.markets,
    uploadedDocumentCount: value.uploaded_document_count,
    uploadedFileNames: value.uploaded_file_names,
    factsConfirmed: value.facts_confirmed,
    firstOutcome: value.first_outcome,
    completedAt: value.completed_at,
    dismissedUntil: value.dismissed_until,
  };
  return Object.fromEntries(
    Object.entries(mapped).filter(([, item]) => item !== undefined),
  ) as Partial<ActivationState>;
}

function toServer(value: Partial<ActivationState>) {
  const mapped = {
    step: value.step,
    company_name: value.companyName,
    instrument_families: value.instrumentFamilies,
    markets: value.markets,
    uploaded_document_count: value.uploadedDocumentCount,
    uploaded_file_names: value.uploadedFileNames,
    facts_confirmed: value.factsConfirmed,
    first_outcome: value.firstOutcome,
    completed_at: value.completedAt,
    dismissed_until: value.dismissedUntil,
  };
  return Object.fromEntries(Object.entries(mapped).filter(([, item]) => item !== undefined));
}

export function useActivationState() {
  const { profile, user } = useAuth();
  const scope = useMemo(
    () => profile?.organization_id || user?.id || 'workspace',
    [profile?.organization_id, user?.id],
  );
  const [state, setState] = useState<ActivationState>(() => readActivationState(scope));

  useEffect(() => {
    setState(readActivationState(scope));
    let cancelled = false;
    void httpClient.get('/api/onboarding/activation', { silentError: true })
      .then((response) => {
        if (cancelled) return;
        const outer = response.data as { data?: unknown };
        const payload = outer?.data;
        const remote = payload && typeof payload === 'object' && 'data' in payload
          ? (payload as { data?: ServerActivationState }).data
          : payload as ServerActivationState | undefined;
        if (!remote) return;
        setState((current) => mergeActivationState(scope, current, fromServer(remote)));
      })
      .catch(() => undefined);
    return () => { cancelled = true; };
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
    void httpClient.patch('/api/onboarding/activation', toServer(patch), { silentError: true })
      .catch(() => undefined);
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

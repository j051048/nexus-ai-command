import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ACTIVATION_UPDATED_EVENT,
  activationProgress,
  DEFAULT_ACTIVATION_STATE,
  isActivationComplete,
  mergeActivationState,
  readActivationState,
  writeActivationState,
} from '@/features/activation/activationState';

describe('activationState', () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    vi.mocked(window.localStorage.getItem).mockImplementation((key) => storage.get(key) ?? null);
    vi.mocked(window.localStorage.setItem).mockImplementation((key, value) => { storage.set(key, value); });
    vi.mocked(window.localStorage.removeItem).mockImplementation((key) => { storage.delete(key); });
    vi.mocked(window.localStorage.clear).mockImplementation(() => { storage.clear(); });
    window.localStorage.clear();
  });

  it('isolates activation progress by organization scope', () => {
    writeActivationState('org-a', {
      ...DEFAULT_ACTIVATION_STATE,
      companyName: 'A 公司',
      step: 'review',
    });

    expect(readActivationState('org-a').companyName).toBe('A 公司');
    expect(readActivationState('org-b')).toEqual(DEFAULT_ACTIVATION_STATE);
  });

  it('broadcasts updates and preserves normalized arrays', () => {
    const listener = vi.fn();
    window.addEventListener(ACTIVATION_UPDATED_EVENT, listener);
    const current = readActivationState('org-a');
    const next = mergeActivationState('org-a', current, {
      instrumentFamilies: ['spectroscopy'],
      uploadedFileNames: ['产品彩页.pdf'],
    });

    expect(next.instrumentFamilies).toEqual(['spectroscopy']);
    expect(readActivationState('org-a').uploadedFileNames).toEqual(['产品彩页.pdf']);
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(ACTIVATION_UPDATED_EVENT, listener);
  });

  it('migrates users who completed the legacy product tour without interrupting them', () => {
    window.localStorage.setItem('nexus_onboarding_completed', 'true');
    const state = readActivationState('org-existing');

    expect(isActivationComplete(state)).toBe(true);
    expect(state.step).toBe('complete');
  });

  it('reports stable progress for every activation step', () => {
    expect(activationProgress('knowledge')).toBe(0);
    expect(activationProgress('first_value')).toBe(3);
    expect(activationProgress('complete')).toBe(4);
  });
});

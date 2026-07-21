export const ACTIVATION_UPDATED_EVENT = 'nexus:activation-updated';
export const ACTIVATION_OPEN_EVENT = 'nexus:activation-open';

export type ActivationStep = 'knowledge' | 'organize' | 'review' | 'first_value' | 'complete';
export type InstrumentFamily = 'spectroscopy' | 'chromatography' | 'mass_spectrometry' | 'energy_spectroscopy' | 'electronics';

export const INSTRUMENT_FAMILY_LABELS: Record<InstrumentFamily, string> = {
  spectroscopy: '光谱',
  chromatography: '色谱',
  mass_spectrometry: '质谱',
  energy_spectroscopy: '能谱',
  electronics: '电子仪器',
};

export interface ActivationState {
  version: 1;
  step: ActivationStep;
  companyName: string;
  instrumentFamilies: InstrumentFamily[];
  markets: string;
  uploadedDocumentCount: number;
  uploadedFileNames: string[];
  factsConfirmed: boolean;
  firstOutcome?: 'solution' | 'tender' | 'opportunity';
  completedAt?: string;
  dismissedUntil?: string;
}

const STORAGE_PREFIX = 'nexus:activation:v1';
const LEGACY_COMPLETION_KEYS = ['nexus_onboarding_completed', 'hasSeenTour'] as const;

export const DEFAULT_ACTIVATION_STATE: ActivationState = {
  version: 1,
  step: 'knowledge',
  companyName: '',
  instrumentFamilies: [],
  markets: '',
  uploadedDocumentCount: 0,
  uploadedFileNames: [],
  factsConfirmed: false,
};

function normalizeScope(scope?: string | null) {
  return (scope || 'workspace').replace(/[^a-zA-Z0-9_-]/g, '_');
}

function storageKey(scope?: string | null) {
  return `${STORAGE_PREFIX}:${normalizeScope(scope)}`;
}

function legacyOnboardingWasCompleted() {
  if (typeof window === 'undefined') return false;
  if (LEGACY_COMPLETION_KEYS.some((key) => window.localStorage.getItem(key) === 'true')) return true;
  try {
    const legacy = JSON.parse(window.localStorage.getItem('nexus_onboarding') || '{}') as { completed?: boolean };
    return legacy.completed === true;
  } catch {
    return false;
  }
}

export function readActivationState(scope?: string | null): ActivationState {
  if (typeof window === 'undefined') return DEFAULT_ACTIVATION_STATE;
  const key = storageKey(scope);
  try {
    const raw = window.localStorage.getItem(key);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<ActivationState>;
      return {
        ...DEFAULT_ACTIVATION_STATE,
        ...parsed,
        instrumentFamilies: Array.isArray(parsed.instrumentFamilies) ? parsed.instrumentFamilies : [],
        uploadedFileNames: Array.isArray(parsed.uploadedFileNames) ? parsed.uploadedFileNames : [],
      };
    }
    if (legacyOnboardingWasCompleted()) {
      const migrated: ActivationState = {
        ...DEFAULT_ACTIVATION_STATE,
        step: 'complete',
        factsConfirmed: true,
        completedAt: new Date().toISOString(),
      };
      window.localStorage.setItem(key, JSON.stringify(migrated));
      return migrated;
    }
  } catch {
    return DEFAULT_ACTIVATION_STATE;
  }
  return DEFAULT_ACTIVATION_STATE;
}

export function writeActivationState(scope: string | null | undefined, next: ActivationState) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(storageKey(scope), JSON.stringify(next));
  window.dispatchEvent(new CustomEvent(ACTIVATION_UPDATED_EVENT, { detail: { scope, state: next } }));
}

export function mergeActivationState(
  scope: string | null | undefined,
  current: ActivationState,
  patch: Partial<ActivationState>,
) {
  const next = { ...current, ...patch, version: 1 as const };
  writeActivationState(scope, next);
  return next;
}

export function activationProgress(step: ActivationStep) {
  return Math.max(0, ['knowledge', 'organize', 'review', 'first_value', 'complete'].indexOf(step));
}

export function isActivationComplete(state: ActivationState) {
  return state.step === 'complete' || Boolean(state.completedAt);
}

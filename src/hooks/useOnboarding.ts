import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/integrations/supabase/client';

const STORAGE_KEY = 'nexus_onboarding';

interface OnboardingState {
  currentStep: number;
  completedSteps: number[];
  onboardingCompleted: boolean;
  stepData: Record<string, unknown>;
}

const DEFAULT_STATE: OnboardingState = {
  currentStep: 0,
  completedSteps: [],
  onboardingCompleted: false,
  stepData: {},
};

function loadLocalState(): OnboardingState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return { ...DEFAULT_STATE, ...JSON.parse(raw) };
    }
  } catch {
    // ignore parse errors
  }
  return DEFAULT_STATE;
}

function saveLocalState(state: OnboardingState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore storage errors
  }
}

/**
 * useOnboarding - 管理新用户引导流程
 *
 * 功能：
 * - 检查用户是否需要引导（onboarding_completed 标记）
 * - 跟踪已完成的步骤
 * - 状态持久化到 localStorage + 后端
 */
export function useOnboarding() {
  const [state, setState] = useState<OnboardingState>(loadLocalState);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [loading, setLoading] = useState(true);

  // Check if user needs onboarding on mount
  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const {
          data: { user },
        } = await supabase.auth.getUser();

        if (!user) {
          setNeedsOnboarding(false);
          setLoading(false);
          return;
        }

        // Check user metadata for onboarding_completed flag
        const metadata = user.user_metadata ?? {};
        const completed = metadata.onboarding_completed === true;

        if (!cancelled) {
          if (completed) {
            setNeedsOnboarding(false);
            setState((prev) => ({ ...prev, onboardingCompleted: true }));
          } else {
            // Also check localStorage in case backend sync failed
            const local = loadLocalState();
            setNeedsOnboarding(!local.onboardingCompleted);
          }
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          // On error, fall back to localStorage
          const local = loadLocalState();
          setNeedsOnboarding(!local.onboardingCompleted);
          setLoading(false);
        }
      }
    }

    check();
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist state changes to localStorage
  useEffect(() => {
    saveLocalState(state);
  }, [state]);

  const setCurrentStep = useCallback((step: number) => {
    setState((prev) => ({
      ...prev,
      currentStep: step,
      completedSteps: prev.completedSteps.includes(prev.currentStep)
        ? prev.completedSteps
        : [...prev.completedSteps, prev.currentStep],
    }));
  }, []);

  const saveStepData = useCallback(
    async (stepKey: string, data: unknown) => {
      setState((prev) => ({
        ...prev,
        stepData: { ...prev.stepData, [stepKey]: data },
      }));

      // Optionally sync to backend
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (session?.access_token) {
          const backendUrl = import.meta.env.VITE_BACKEND_URL || '';
          await fetch(`${backendUrl}/api/onboarding/step`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${session.access_token}`,
            },
            body: JSON.stringify({ step: stepKey, data }),
          }).catch(() => {
            // Silently fail - localStorage is the primary store
          });
        }
      } catch {
        // Backend sync is best-effort
      }
    },
    [],
  );

  const completeOnboarding = useCallback(async () => {
    setState((prev) => ({ ...prev, onboardingCompleted: true }));
    setNeedsOnboarding(false);

    // Update user metadata in Supabase Auth
    try {
      await supabase.auth.updateUser({
        data: { onboarding_completed: true },
      });
    } catch {
      // If Supabase update fails, localStorage still has the flag
    }

    // Notify backend
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (session?.access_token) {
        const backendUrl = import.meta.env.VITE_BACKEND_URL || '';
        await fetch(`${backendUrl}/api/onboarding/complete`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session.access_token}`,
          },
          body: JSON.stringify({ step_data: state.stepData }),
        }).catch(() => {});
      }
    } catch {
      // Best-effort
    }
  }, [state.stepData]);

  const resetOnboarding = useCallback(() => {
    setState(DEFAULT_STATE);
    setNeedsOnboarding(true);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return {
    needsOnboarding,
    loading,
    currentStep: state.currentStep,
    completedSteps: state.completedSteps,
    onboardingCompleted: state.onboardingCompleted,
    stepData: state.stepData,
    setCurrentStep,
    saveStepData,
    completeOnboarding,
    resetOnboarding,
  };
}

export default useOnboarding;

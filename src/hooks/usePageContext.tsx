/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useCallback, useRef, useState } from 'react';
import { INSTRUMENT_FAMILY_LABELS } from '@/features/activation/activationState';
import { useActivationState } from '@/hooks/useActivationState';

export interface PageContextData {
  type: string;       // 'customer' | 'approval' | 'project' | 'dashboard' | ...
  id?: string;        // entity ID
  name?: string;      // entity display name
  metadata?: Record<string, unknown>;
}

interface PageContextValue {
  pageContext: PageContextData | null;
  setPageContext: (ctx: PageContextData) => void;
  clearPageContext: () => void;
  /** Format context as a prefix for AI messages */
  formatContextPrefix: () => string;
}

const PageContext = createContext<PageContextValue>({
  pageContext: null,
  setPageContext: () => {},
  clearPageContext: () => {},
  formatContextPrefix: () => '',
});

export function PageContextProvider({ children }: { children: React.ReactNode }) {
  const { state: activationState } = useActivationState();
  const [pageContext, setPageContextState] = useState<PageContextData | null>(null);
  const contextRef = useRef<PageContextData | null>(null);

  const setPageContext = useCallback((ctx: PageContextData) => {
    contextRef.current = ctx;
    setPageContextState(ctx);
  }, []);

  const clearPageContext = useCallback(() => {
    contextRef.current = null;
    setPageContextState(null);
  }, []);

  const formatContextPrefix = useCallback(() => {
    const ctx = contextRef.current;
    const prefixes: string[] = [];
    const families = activationState.instrumentFamilies.map((item) => INSTRUMENT_FAMILY_LABELS[item]).join('、');
    if (activationState.companyName || families || activationState.markets) {
      const enterprise = [activationState.companyName, families, activationState.markets].filter(Boolean).join('；');
      prefixes.push(`[企业上下文: ${enterprise}]`);
    }
    if (ctx) {
      const parts = [`[当前页面: ${ctx.type}`];
      if (ctx.name) parts.push(` - ${ctx.name}`);
      if (ctx.id) parts.push(` #${ctx.id.slice(0, 8)}`);
      parts.push(']');
      prefixes.push(parts.join(''));
    }
    return prefixes.join(' ');
  }, [activationState.companyName, activationState.instrumentFamilies, activationState.markets]);

  return (
    <PageContext.Provider value={{ pageContext, setPageContext, clearPageContext, formatContextPrefix }}>
      {children}
    </PageContext.Provider>
  );
}

export function usePageContext() {
  return useContext(PageContext);
}

/**
 * Hook for business pages to register their context.
 * Automatically clears on unmount.
 */
export function useRegisterPageContext(ctx: PageContextData | null) {
  const { setPageContext, clearPageContext } = usePageContext();
  const prevRef = useRef<string>('');

  React.useEffect(() => {
    if (!ctx) return;
    const key = `${ctx.type}:${ctx.id ?? ''}`;
    if (key === prevRef.current) return;
    prevRef.current = key;
    setPageContext(ctx);
    return () => {
      prevRef.current = '';
      clearPageContext();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx?.type, ctx?.id, ctx?.name, setPageContext, clearPageContext]);
}

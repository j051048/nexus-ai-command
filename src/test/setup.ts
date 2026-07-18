import '@testing-library/jest-dom';
import { vi } from 'vitest';

const guardedFetch = vi.fn(async (input: RequestInfo | URL) => {
  const url = typeof input === 'string' ? input : input.toString();
  throw new Error(
    `Unexpected network request in frontend test: ${url}. Mock fetch or the API client explicitly.`
  );
});

Object.defineProperty(globalThis, 'fetch', {
  configurable: true,
  writable: true,
  value: guardedFetch,
});

// Fix for jsdom/vitest environment
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => {},
    }),
  });

  Object.defineProperty(window, 'localStorage', {
    value: {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    },
  });

  // ResizeObserver polyfill for components using it (e.g. ReactFlow, Radix)
  if (!window.ResizeObserver) {
    window.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof globalThis.ResizeObserver;
  }
}

// Mock environment variables for Supabase
// In Vitest, we can also use vi.stubEnv
vi.stubEnv('VITE_SUPABASE_URL', 'https://mock-project.supabase.co');
vi.stubEnv('VITE_SUPABASE_PUBLISHABLE_KEY', 'mock-anon-key');

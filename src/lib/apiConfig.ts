/**
 * Unified API Base URL resolver.
 *
 * Replaces the "Robust URL Discovery" pattern duplicated across 6+ files.
 * Single source of truth: reads VITE_API_BASE_URL, normalises protocol,
 * and falls back to localhost in dev or current origin in production.
 *
 * Environment isolation guard: preview and staging builds deployed behind the
 * production rewrite must never fall back to the same-origin API, otherwise a
 * PR preview would silently write to production data. Those environments must
 * declare VITE_API_BASE_URL explicitly.
 */
const ISOLATED_ENVIRONMENTS = new Set(['preview', 'staging']);

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;

  if (configured) {
    const url = configured.startsWith('http') ? configured : `https://${configured}`;
    return url.replace(/\/$/, '');
  }

  const appEnv = String(import.meta.env.VITE_APP_ENV || '').toLowerCase();
  if (ISOLATED_ENVIRONMENTS.has(appEnv)) {
    throw new Error(
      `VITE_API_BASE_URL is required when VITE_APP_ENV=${appEnv}; ` +
        'refusing to reuse the production API endpoint from a non-production environment.',
    );
  }

  // Fallback: localhost in dev, same origin in production
  const hostname = window.location.hostname;
  return hostname === 'localhost' || hostname === '127.0.0.1'
    ? `http://${hostname}:8000`
    : window.location.origin;
}

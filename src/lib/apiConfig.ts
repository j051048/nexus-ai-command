/**
 * Unified API Base URL resolver.
 *
 * Replaces the "Robust URL Discovery" pattern duplicated across 6+ files.
 * Single source of truth: reads VITE_API_BASE_URL, normalises protocol,
 * and falls back to localhost in dev or current origin in production.
 */
export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;

  if (configured) {
    const url = configured.startsWith('http') ? configured : `https://${configured}`;
    return url.replace(/\/$/, '');
  }

  // Fallback: localhost in dev, same origin in production
  const hostname = window.location.hostname;
  return hostname === 'localhost' || hostname === '127.0.0.1'
    ? `http://${hostname}:8000`
    : window.location.origin;
}

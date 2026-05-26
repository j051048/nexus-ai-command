/**
 * Core Web Vitals reporting — sends CLS, INP, LCP, FCP, TTFB to Sentry
 * with rating-based severity and optional custom endpoint.
 *
 * P0 Audit fix: Added rating classification, console dev logging,
 * and custom endpoint support via VITE_VITALS_ENDPOINT.
 */
import type { Metric } from 'web-vitals';
import { getApiBaseUrl } from './apiConfig';

const IS_PROD = import.meta.env.PROD;
const REPORT_ENDPOINT = import.meta.env.VITE_VITALS_ENDPOINT || `${getApiBaseUrl()}/api/metrics/web-vitals`;
const WEB_VITAL_RATINGS = new Set(['good', 'needs-improvement', 'poor']);

function normalizeRating(rating: Metric['rating'] | undefined): string {
  return rating && WEB_VITAL_RATINGS.has(rating) ? rating : 'unknown';
}

function reportMetric(metric: Metric): void {
  const rating = normalizeRating(metric.rating);
  const payload = {
    name: metric.name,
    value: Math.round(metric.name === 'CLS' ? metric.value * 1000 : metric.value),
    rating,
    id: metric.id,
    path: window.location.pathname,
  };

  // Dev: rich console output with color-coded rating
  if (!IS_PROD) {
    const color = rating === 'good' ? '#0CCE6B'
      : rating === 'needs-improvement' ? '#FFA400' : '#FF4E42';
    console.log(
      `%c[WebVitals] ${metric.name}: ${payload.value} (${rating})`,
      `color: ${color}; font-weight: bold;`
    );
    return;
  }

  // Sentry integration
  try {
    import('@sentry/react').then((Sentry) => {
      Sentry.setMeasurement(metric.name, metric.value, metric.name === 'CLS' ? '' : 'millisecond');
      // Tag poor metrics for Sentry alerting
      if (rating === 'poor') {
        Sentry.setTag(`webvitals.${metric.name}`, 'poor');
      }
    }).catch(() => {});
  } catch {
    // Sentry not available
  }

  // Backend endpoint feeds Prometheus/in-memory SLO dashboards.
  if (REPORT_ENDPOINT) {
    const body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon(REPORT_ENDPOINT, blob);
    } else {
      fetch(REPORT_ENDPOINT, {
        method: 'POST',
        body,
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        keepalive: true,
      }).catch(() => {});
    }
  }
}

export function reportWebVitals() {
  // Dynamic import to avoid blocking first paint
  import('web-vitals').then(({ onCLS, onINP, onLCP, onFCP, onTTFB }) => {
    onCLS(reportMetric);
    onINP(reportMetric);
    onLCP(reportMetric);
    onFCP(reportMetric);
    onTTFB(reportMetric);
  }).catch(() => {
    // web-vitals not available — silently skip
  });
}

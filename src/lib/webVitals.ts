/**
 * Core Web Vitals reporting — sends CLS, INP, LCP, FCP, TTFB to Sentry.
 * Only active in production builds.
 */
import { onCLS, onINP, onLCP, onFCP, onTTFB } from 'web-vitals';

export function reportWebVitals() {
  if (import.meta.env.MODE !== 'production') return;

  try {
    // Dynamically import Sentry to avoid bundling issues if not configured
    import('@sentry/react').then((Sentry) => {
      const report = ({ name, value, id }: { name: string; value: number; id: string }) => {
        // Use Sentry's custom measurement API
        Sentry.setMeasurement(name, value, name === 'CLS' ? '' : 'millisecond');
      };

      onCLS(report);
      onINP(report);
      onLCP(report);
      onFCP(report);
      onTTFB(report);
    }).catch(() => {
      // Sentry not available — silently skip
    });
  } catch {
    // web-vitals or Sentry not available
  }
}

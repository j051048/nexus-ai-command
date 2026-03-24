/**
 * Re-export from the canonical mobile detection hook.
 *
 * `use-mobile.tsx` (useIsMobile) is the primary hook used across the codebase.
 * This file keeps backward compatibility for any imports from `useMobile`.
 */
export { useIsMobile, useIsTablet, useDeviceType } from './use-mobile';
export type { DeviceType } from './use-mobile';

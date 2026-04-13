import * as React from "react";

const MOBILE_BREAKPOINT = 768;
const TABLET_BREAKPOINT = 1024;

// P0 #18: Sync-initialize to prevent layout flicker on first render.
// useState(undefined) → !!undefined = false, causing a flash when switching
// from desktop to mobile layout after hydration.
function _getInitialMobile(): boolean {
  if (typeof window === "undefined") return false;
  return window.innerWidth < MOBILE_BREAKPOINT;
}

function _getInitialTablet(): boolean {
  if (typeof window === "undefined") return false;
  const w = window.innerWidth;
  return w >= MOBILE_BREAKPOINT && w < TABLET_BREAKPOINT;
}

export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean>(_getInitialMobile);

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    };
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return isMobile;
}

export function useIsTablet() {
  const [isTablet, setIsTablet] = React.useState<boolean>(_getInitialTablet);

  React.useEffect(() => {
    const check = () => {
      const w = window.innerWidth;
      setIsTablet(w >= MOBILE_BREAKPOINT && w < TABLET_BREAKPOINT);
    };
    const mqlMin = window.matchMedia(`(min-width: ${MOBILE_BREAKPOINT}px)`);
    const mqlMax = window.matchMedia(`(max-width: ${TABLET_BREAKPOINT - 1}px)`);
    const onChange = () => check();
    mqlMin.addEventListener("change", onChange);
    mqlMax.addEventListener("change", onChange);
    return () => {
      mqlMin.removeEventListener("change", onChange);
      mqlMax.removeEventListener("change", onChange);
    };
  }, []);

  return isTablet;
}

export type DeviceType = 'mobile' | 'tablet' | 'desktop';

export function useDeviceType(): DeviceType {
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  if (isMobile) return 'mobile';
  if (isTablet) return 'tablet';
  return 'desktop';
}

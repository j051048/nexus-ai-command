import * as React from "react";

export type Orientation = 'portrait' | 'landscape';

/**
 * 检测屏幕方向（竖屏/横屏）
 * 基于 CSS media query，实时响应方向变化
 */
export function useOrientation(): Orientation {
  const [orientation, setOrientation] = React.useState<Orientation>('portrait');

  React.useEffect(() => {
    const mql = window.matchMedia('(orientation: portrait)');
    const onChange = (e: MediaQueryListEvent | MediaQueryList) => {
      setOrientation(e.matches ? 'portrait' : 'landscape');
    };
    onChange(mql);
    mql.addEventListener('change', onChange as (e: MediaQueryListEvent) => void);
    return () => mql.removeEventListener('change', onChange as (e: MediaQueryListEvent) => void);
  }, []);

  return orientation;
}

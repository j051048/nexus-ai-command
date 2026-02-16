/**
 * @deprecated 此组件已被 MobileTabBar.tsx 替代。
 * 请使用 import MobileTabBar from '@/components/mobile/MobileTabBar';
 * 将在后续版本中删除。
 */

export default function MobileNavBar() {
  if (import.meta.env.DEV) {
    console.warn('[MobileNavBar] 已废弃，请使用 MobileTabBar 代替');
  }
  return null;
}

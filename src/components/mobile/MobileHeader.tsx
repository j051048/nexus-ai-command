/**
 * @deprecated 此组件已被 MobilePageHeader.tsx 替代。
 * 请使用 import MobilePageHeader from '@/components/mobile/MobilePageHeader';
 * 将在后续版本中删除。
 */

export default function MobileHeader() {
  if (import.meta.env.DEV) {
    console.warn('[MobileHeader] 已废弃，请使用 MobilePageHeader 代替');
  }
  return null;
}

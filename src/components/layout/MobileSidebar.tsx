/**
 * @deprecated 此组件已被 MobileWorkbenchPage + MobileTabBar 替代。
 * 移动端导航功能已迁移到 MobileLayout 架构。
 * 将在后续版本中删除。
 */

import React from 'react';

interface MobileSidebarProps {
  children?: React.ReactNode;
}

export function MobileSidebar({ children }: MobileSidebarProps) {
  if (import.meta.env.DEV) {
    console.warn('[MobileSidebar] 已废弃，功能已迁移到 MobileLayout 体系');
  }
  return null;
}

export default MobileSidebar;

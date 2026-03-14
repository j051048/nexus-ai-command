/**
 * 移动端核心 Layout
 * 底部 Tab 路由 + 全屏页面 + AI 半屏伴随
 * 替代移动端的 ChatFirstLayout
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useMobileNavigation } from '@/hooks/useMobileNavigation';
import { cn } from '@/lib/utils';
import MobileTabBar from '@/components/mobile/MobileTabBar';
import MobilePageHeader from '@/components/mobile/MobilePageHeader';
import MobileAISheet from '@/components/mobile/MobileAISheet';
import MobileAIFAB from '@/components/mobile/MobileAIFAB';
import { CommandPalette } from '@/components/common/CommandPalette';
import { InstallPrompt } from '@/components/common/InstallPrompt';

// Sprint 3: 移动端专属首页 + 工作台
import MobileHomePage from '@/components/mobile/MobileHomePage';
import MobileWorkbenchPage from '@/components/mobile/MobileWorkbenchPage';

// Sprint 4: 个人中心
import MobileProfilePage from '@/components/mobile/MobileProfilePage';

import { useWebSocketPush } from '@/hooks/useWebSocketPush';

export function MobileLayout() {
  const location = useLocation();
  const [isAISheetOpen, setIsAISheetOpen] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const { activeTab, isSubPage, getPageTitle, navigateToTab, goBack } = useMobileNavigation();

  // 实时推送连接（WebSocket + 自动重连）
  useWebSocketPush();

  // 页面转场动画
  const prevPathRef = useRef(location.pathname);
  const [transitionClass, setTransitionClass] = useState('');

  useEffect(() => {
    const prev = prevPathRef.current;
    const curr = location.pathname;

    if (prev !== curr) {
      // 子页面进入 → slide-in-right，Tab 切换 → fade-in
      const isGoingDeeper = curr.split('/').length > prev.split('/').length;
      setTransitionClass(isGoingDeeper ? 'animate-slide-in-right' : 'animate-mobile-fade-in');
      prevPathRef.current = curr;

      // 动画完成后清除 class
      const timer = setTimeout(() => setTransitionClass(''), 400);
      return () => clearTimeout(timer);
    }
  }, [location.pathname]);

  const handleAIPress = useCallback(() => {
    setIsAISheetOpen(true);
  }, []);

  const handleSearch = useCallback(() => {
    setIsCommandPaletteOpen(true);
  }, []);

  // 渲染主内容区：首页/工作台使用专属移动端页面，其他路由用 Outlet
  const renderContent = () => {
    const path = location.pathname;

    // 首页 → 移动端专属首页
    if (path === '/dashboard' || path === '/boss-dashboard') {
      return <MobileHomePage />;
    }

    // 工作台默认页 → 移动端功能卡片网格
    if (activeTab === 'workbench' && path === '/approval') {
      return <MobileWorkbenchPage />;
    }

    // Sprint 4: 个人中心
    if (path === '/profile') {
      return <MobileProfilePage />;
    }

    return <Outlet />;
  };

  return (
    <div className="flex flex-col h-[100dvh] w-full bg-background overflow-hidden">
      {/* 顶部导航栏 */}
      <MobilePageHeader
        title={getPageTitle(location.pathname)}
        showBack={isSubPage}
        onBack={goBack}
        onAIPress={handleAIPress}
        onSearch={handleSearch}
      />

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto pb-[calc(3.5rem+env(safe-area-inset-bottom))]">
        <div className={cn("min-h-full", transitionClass)}>
          {renderContent()}
        </div>
      </main>

      {/* AI 浮动按钮（仅在子页面时显示） */}
      {isSubPage && (
        <MobileAIFAB onClick={handleAIPress} />
      )}

      {/* 底部 Tab 栏 */}
      <MobileTabBar
        activeTab={activeTab}
        onTabChange={navigateToTab}
        onAIPress={handleAIPress}
      />

      {/* AI 半屏浮窗 */}
      <MobileAISheet
        isOpen={isAISheetOpen}
        onClose={() => setIsAISheetOpen(false)}
      />

      {/* 命令面板 */}
      <CommandPalette
        open={isCommandPaletteOpen}
        onOpenChange={setIsCommandPaletteOpen}
        onAIChat={() => {
          setIsCommandPaletteOpen(false);
          setIsAISheetOpen(true);
        }}
      />

      {/* PWA 安装提示 */}
      <InstallPrompt />
    </div>
  );
}

export default MobileLayout;

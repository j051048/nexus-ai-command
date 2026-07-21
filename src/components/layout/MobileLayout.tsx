/**
 * 移动端核心 Layout
 * 底部 Tab 路由 + 全屏页面 + AI 半屏伴随
 * 替代移动端的 ChatFirstLayout
 */

import React, { useState, useCallback, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useMobileNavigation } from '@/hooks/useMobileNavigation';
import MobileTabBar from '@/components/mobile/MobileTabBar';
import MobilePageHeader from '@/components/mobile/MobilePageHeader';
import MobileAISheet from '@/components/mobile/MobileAISheet';
import MobileAIFAB from '@/components/mobile/MobileAIFAB';
import { CommandPalette } from '@/components/common/CommandPalette';
import { InstallPrompt } from '@/components/common/InstallPrompt';
import { DeliverableCenter } from '@/components/deliverables/DeliverableCenter';

// Sprint 3: 移动端专属首页 + 工作台
import MobileHomePage from '@/components/mobile/MobileHomePage';
import MobileWorkbenchPage from '@/components/mobile/MobileWorkbenchPage';
import InboxPage from '@/pages/InboxPage';

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

  const handleAIPress = useCallback(() => {
    setIsAISheetOpen(true);
  }, []);

  const handleVoiceMemoPress = useCallback(() => {
    window.dispatchEvent(
      new CustomEvent('proactive-chat', {
        detail: {
          message:
            '我刚完成一次客户拜访，请用语音速记模式帮我提取：客户名称、参会人、需求、异议、下一步动作和跟进日期。',
        },
      }),
    );
    setIsAISheetOpen(true);
  }, []);

  // 监听后台 AI 主动对话事件 → 自动打开 AI 浮窗
  useEffect(() => {
    const handler = () => setIsAISheetOpen(true);
    window.addEventListener('proactive-chat', handler);
    return () => window.removeEventListener('proactive-chat', handler);
  }, []);

  const handleSearch = useCallback(() => {
    setIsCommandPaletteOpen(true);
  }, []);

  // 渲染主内容区：首页/工作台使用专属移动端页面，其他路由用 Outlet
  const renderContent = () => {
    const path = location.pathname;
    const renderActionInbox = () => {
      return <InboxPage />;
    };

    // 行动台是移动端默认首页，和桌面统一使用同一套行动模型。
    if (path === '/dashboard') {
      return (
        <div className="px-4 pb-24 pt-4">
          {renderActionInbox()}
        </div>
      );
    }

    // Boss 总控仍保留移动端概览。
    if (path === '/boss-dashboard') {
      return <MobileHomePage />;
    }

    // 工作台默认页 → 移动端功能卡片网格
    if (path === '/workbench') {
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
        rightActions={<DeliverableCenter iconOnly />}
      />

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto pb-[calc(3.5rem+env(safe-area-inset-bottom))]">
        <div className="min-h-full">
          {renderContent()}
        </div>
      </main>

      {/* AI 浮动按钮（仅在子页面时显示） */}
      {isSubPage && (
        <MobileAIFAB onClick={handleAIPress} onLongPress={handleVoiceMemoPress} />
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

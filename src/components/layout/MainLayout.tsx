import React, { useState, useCallback } from 'react';
import { Sidebar } from './Sidebar';
import { MobileSidebar } from './MobileSidebar';
import { ActiveCardStream } from '../cards/ActiveCardStream';
import { AIChatPanel } from '../ai/AIChatPanel';
import { useUser } from '@/contexts/UserContext';
import { Menu, X, Command } from 'lucide-react';
import { useIsMobile } from '@/hooks/use-mobile';
import { NotificationCenter } from '../common/NotificationCenter';
import { useLocation } from 'react-router-dom';
import { CommandPalette } from '../common/CommandPalette';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { useTheme } from '@/contexts/ThemeContext';
import { Button } from '@/components/ui/button';

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const { user } = useUser();
  const { toggleTheme } = useTheme();
  const [isChatExpanded, setIsChatExpanded] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isCardsOpen, setIsCardsOpen] = useState(false);
  const [isCommandOpen, setIsCommandOpen] = useState(false);
  const isMobile = useIsMobile();
  const location = useLocation();

  // 快捷键回调
  const toggleAIChat = useCallback(() => {
    setIsChatExpanded(prev => !prev);
  }, []);

  const openCommandPalette = useCallback(() => {
    setIsCommandOpen(true);
  }, []);

  const toggleSidebar = useCallback(() => {
    setIsSidebarOpen(prev => !prev);
  }, []);

  // 注册全局快捷键
  useKeyboardShortcuts({
    toggleAIChat,
    openCommandPalette,
    toggleSidebar,
    toggleTheme,
  });

  // AI 聊天回调
  const handleAIChat = useCallback((message: string) => {
    setIsChatExpanded(true);
    // TODO: 将消息发送到 AI 聊天面板
    console.log('AI Chat:', message);
  }, []);

  // Simple mapping for titles based on path
  const getPageTitle = () => {
    const path = location.pathname;
    if (path.includes('boss-dashboard')) return '总控中心';
    if (path.includes('dashboard')) return '战绩中心';
    if (path.includes('sales')) return '销售管道';
    if (path.includes('projects')) return '项目管理';
    if (path.includes('tender-analysis')) return '标书审阅';
    if (path.includes('battlecards')) return '竞品库';
    if (path.includes('target-dashboard')) return '目标看板';
    if (path.includes('approval')) return '智能审批';
    if (path.includes('knowledge')) return '知识库';
    if (path.includes('documents')) return '文档中心';
    if (path.includes('rewards')) return '激励钱包';
    if (path.includes('settings')) return '系统设置';
    if (path.includes('employees')) return '员工管理';
    if (path.includes('exceptions')) return '异常待办';
    if (path.includes('targets')) return '目标管理';

    return 'Nexus OS';
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
            {/* Command Palette - 全局命令面板 */}
      <CommandPalette
        open={isCommandOpen}
        onOpenChange={setIsCommandOpen}
        onAIChat={handleAIChat}
      />

      {/* Mobile Header */}
      {isMobile && (
        <div className="fixed top-0 left-0 right-0 h-14 bg-card/95 backdrop-blur-sm border-b border-border z-40 flex items-center justify-between px-4">
          <MobileSidebar />
          <span className="font-semibold text-foreground">Project Nexus</span>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9"
              onClick={() => setIsCommandOpen(true)}
            >
              <Command className="w-4 h-4" />
              <span className="sr-only">命令面板</span>
            </Button>
            <NotificationCenter />
            <button onClick={() => setIsCardsOpen(true)} className="p-2 hover:bg-secondary rounded-lg relative">
              <span className="w-2 h-2 rounded-full bg-success absolute top-1 right-1 animate-pulse" />
              <Menu className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Desktop Sidebar */}
      {!isMobile && <Sidebar />}

      {/* Main Content Area */}
      <div className={`${isMobile ? 'pt-14 pb-20' : 'ml-64 mr-80'} min-h-screen flex flex-col transition-all duration-300`}>
                {/* Desktop Header */}
        {!isMobile && (
          <header className="h-16 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-30 px-6 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground/80">
              {getPageTitle()}
            </h2>
            <div className="flex items-center gap-4">
              {/* 命令面板触发按钮 */}
              <Button
                variant="outline"
                size="sm"
                className="hidden sm:flex items-center gap-2 text-muted-foreground"
                onClick={() => setIsCommandOpen(true)}
              >
                <Command className="w-4 h-4" />
                <span>搜索命令...</span>
                <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground ml-2">
                  <span className="text-xs">⌘</span>K
                </kbd>
              </Button>
              <NotificationCenter />
            </div>
          </header>
        )}

        <main className="p-4 sm:p-6 flex-1 overflow-auto">
          {children}
        </main>
      </div>

      {/* Mobile Cards Overlay */}
      {isMobile && isCardsOpen && (
        <div className="fixed inset-0 bg-black/50 z-50" onClick={() => setIsCardsOpen(false)}>
          <div className="absolute right-0 top-0 w-80 h-full bg-card border-l border-border" onClick={(e) => e.stopPropagation()}>
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h2 className="font-semibold text-foreground flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
                实时动态
              </h2>
              <button onClick={() => setIsCardsOpen(false)} className="p-1 hover:bg-secondary rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <ActiveCardStream />
          </div>
        </div>
      )}

      {/* Desktop Right Panel */}
      {!isMobile && (
        <div className="fixed right-0 top-0 w-80 h-screen border-l border-border bg-card overflow-hidden flex flex-col">
          <div className="p-4 border-b border-border">
            <h2 className="font-semibold text-foreground flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
              实时动态
            </h2>
            <p className="text-xs text-muted-foreground mt-1">AI 主动推送</p>
          </div>
          <ActiveCardStream />
        </div>
      )}

      {/* Bottom AI Chat Panel */}
      <AIChatPanel
        isExpanded={isChatExpanded}
        onToggle={() => setIsChatExpanded(!isChatExpanded)}
      />
    </div>
  );
}

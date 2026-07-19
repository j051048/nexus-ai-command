import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import {
  Clock,
  Columns2,
  GripVertical,
  MessageSquareText,
  PanelLeft,
  PanelRightClose,
  PanelRightOpen,
  PanelsTopLeft,
} from 'lucide-react';

import EnhancedAIChatPanel from '@/components/ai/EnhancedAIChatPanel';
import { GlobalAIBall } from '@/components/ai/GlobalAIBall';
import { useAuth } from '@/components/auth/AuthContext';
import { TrialBanner } from '@/components/billing/TrialBanner';
import { InstallPrompt } from '@/components/common/InstallPrompt';
import { NotificationCenter } from '@/components/common/NotificationCenter';
import { WelcomeTour } from '@/components/common/WelcomeTour';
import { Breadcrumbs } from '@/components/layout/Breadcrumbs';
import { Sidebar } from '@/components/layout/Sidebar';
import { Button } from '@/components/ui/button';
import { useWebSocketPush } from '@/hooks/useWebSocketPush';
import { cn } from '@/lib/utils';

interface ChatFirstLayoutProps {
  children?: React.ReactNode;
}

type WorkspaceMode = 'business' | 'split' | 'assistant';

const CHAT_WIDTH_KEY = 'nexus.ai-workspace-width';
const DEFAULT_CHAT_WIDTH = 560;
const MIN_CHAT_WIDTH = 400;
const MAX_CHAT_WIDTH = 840;
const MIN_BUSINESS_WIDTH = 640;
const CHAT_WIDTH_PRESETS = [420, 560, 720] as const;
const BUSINESS_FOCUS_ROUTES = new Set([
  '/growth/solutions',
  '/growth/tenders',
  '/tender-analysis',
]);

function readStoredChatWidth() {
  if (typeof window === 'undefined') return DEFAULT_CHAT_WIDTH;
  const raw = window.localStorage.getItem(CHAT_WIDTH_KEY);
  if (!raw) return DEFAULT_CHAT_WIDTH;
  const stored = Number(raw);
  return Number.isFinite(stored)
    ? Math.min(MAX_CHAT_WIDTH, Math.max(MIN_CHAT_WIDTH, stored))
    : DEFAULT_CHAT_WIDTH;
}

function getWorkspaceWidth(panel: HTMLDivElement | null) {
  const measuredWidth = panel?.parentElement?.clientWidth ?? 0;
  return measuredWidth > 0 ? measuredWidth : window.innerWidth;
}

function AssistantStatusPill({
  isChatOpen,
  onOpen,
}: {
  isChatOpen: boolean;
  onOpen: () => void;
}) {
  const [isWorking, setIsWorking] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof window.setTimeout> | undefined;
    const handler = () => {
      setIsWorking(true);
      timer = window.setTimeout(() => setIsWorking(false), 3200);
    };
    window.addEventListener('proactive-chat', handler);
    return () => {
      window.removeEventListener('proactive-chat', handler);
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  return (
    <button
      type="button"
      onClick={onOpen}
      className="hidden items-center gap-2 rounded-md border bg-background px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground md:flex"
      aria-label="打开助手面板"
    >
      <span
        className={cn(
          'h-1.5 w-1.5 rounded-full transition-colors',
          isWorking ? 'bg-primary' : 'bg-muted-foreground/50',
        )}
      />
      <span>{isWorking ? '助手正在整理请求' : isChatOpen ? '助手已开启' : '助手待命'}</span>
    </button>
  );
}

export const ChatFirstLayout = ({ children }: ChatFirstLayoutProps) => {
  const [isCanvasOpen, setIsCanvasOpen] = useState(true);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [chatWidth, setChatWidth] = useState(readStoredChatWidth);
  const chatPanelRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const { isPendingBoss } = useAuth();

  useWebSocketPush();

  const getPageTitle = useCallback(() => {
    const path = location.pathname;
    if (path.includes('boss-dashboard')) return '总控中心';
    if (path.includes('performance-dashboard')) return '战绩看板';
    if (path.includes('dashboard')) return '收件箱';
    if (path.includes('workbench')) return '工作台';
    if (path.includes('ai-center')) return '助手';
    if (path.includes('data')) return '数据';
    if (path.includes('crm')) return 'CRM';
    if (path.includes('sales')) return '销售管道';
    if (path.includes('projects')) return '项目管理';
    if (path.includes('approval')) return '智能审批';
    if (path.includes('growth/solutions')) return '方案作战';
    if (path.includes('tender')) return '投标作战';
    if (path.includes('knowledge')) return '知识资产';
    if (path.includes('vmd')) return '虚拟市场部';
    if (path.includes('org-chart')) return '组织架构';
    if (path.includes('settings')) return '系统设置';
    return 'Nexus OS';
  }, [location.pathname]);

  const isPageRoute = location.pathname !== '/' && location.pathname !== '/chat';
  const workspaceMode: WorkspaceMode = !isChatOpen
    ? 'business'
    : !isCanvasOpen
      ? 'assistant'
      : 'split';

  const setWorkspaceMode = useCallback((mode: WorkspaceMode) => {
    setIsChatOpen(mode !== 'business');
    setIsCanvasOpen(mode !== 'assistant');
  }, []);

  const toggleChat = useCallback(() => {
    if (isChatOpen && !isCanvasOpen) setIsCanvasOpen(true);
    setIsChatOpen((open) => !open);
  }, [isCanvasOpen, isChatOpen]);

  const startResize = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const panelLeft = chatPanelRef.current?.getBoundingClientRect().left ?? 0;
    const onMove = (moveEvent: PointerEvent) => {
      const workspaceWidth = getWorkspaceWidth(chatPanelRef.current);
      const viewportMax = Math.max(MIN_CHAT_WIDTH, workspaceWidth - MIN_BUSINESS_WIDTH);
      const nextWidth = Math.min(
        MAX_CHAT_WIDTH,
        viewportMax,
        Math.max(MIN_CHAT_WIDTH, moveEvent.clientX - panelLeft),
      );
      setChatWidth(Math.round(nextWidth));
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, []);

  const cycleChatWidth = useCallback(() => {
    const currentIndex = CHAT_WIDTH_PRESETS.findIndex((preset) => chatWidth < preset + 40);
    const nextPreset = CHAT_WIDTH_PRESETS[(currentIndex + 1) % CHAT_WIDTH_PRESETS.length];
    const workspaceWidth = getWorkspaceWidth(chatPanelRef.current);
    const availableWidth = Math.max(MIN_CHAT_WIDTH, workspaceWidth - MIN_BUSINESS_WIDTH);
    setChatWidth(Math.min(nextPreset, availableWidth, MAX_CHAT_WIDTH));
  }, [chatWidth]);

  const resizeByKeyboard = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const delta = event.key === 'ArrowRight' ? 24 : -24;
    setChatWidth((width) => Math.min(MAX_CHAT_WIDTH, Math.max(MIN_CHAT_WIDTH, width + delta)));
  }, []);

  useEffect(() => {
    window.localStorage.setItem(CHAT_WIDTH_KEY, String(chatWidth));
  }, [chatWidth]);

  useEffect(() => {
    if (isPageRoute) setIsCanvasOpen(true);
  }, [location.pathname, isPageRoute]);

  useEffect(() => {
    const focusBusiness = BUSINESS_FOCUS_ROUTES.has(location.pathname);
    setIsCanvasOpen(true);
    setIsChatOpen(!focusBusiness);
  }, [location.pathname]);

  useEffect(() => {
    const handler = () => setIsChatOpen(true);
    window.addEventListener('proactive-chat', handler);
    return () => window.removeEventListener('proactive-chat', handler);
  }, []);

  return (
    <div className="workspace-canvas flex h-[100dvh] w-full overflow-hidden text-foreground">
      {isPendingBoss && (
        <div className="fixed left-0 right-0 top-0 z-50 flex items-center justify-center gap-2 bg-warning px-4 py-2 text-center text-xs text-warning-foreground">
          <Clock className="h-3.5 w-3.5" />
          账号审核中，当前以普通员工身份运行
        </div>
      )}

      <div className={cn('relative z-20 hidden h-full md:flex', isPendingBoss && 'pt-9')}>
        <Sidebar />
      </div>

      <div className="relative flex flex-1 overflow-hidden">
        <div
          ref={chatPanelRef}
          className={cn(
            'relative z-10 flex h-full shrink-0 flex-col border-r border-border/90 bg-[hsl(var(--panel))] shadow-[var(--shadow-panel)] transition-[width,opacity] duration-200 before:absolute before:inset-x-0 before:top-0 before:z-30 before:h-0.5 before:bg-primary/70',
            !isChatOpen && 'w-0 overflow-hidden opacity-0',
          )}
          style={
            isChatOpen
              ? { width: isCanvasOpen ? `min(${chatWidth}px, 100vw)` : '100%' }
              : undefined
          }
        >
          <EnhancedAIChatPanel
            isExpanded={isChatOpen}
            onToggle={toggleChat}
            variant="embedded"
          />
        </div>

        {isChatOpen && isCanvasOpen && (
          <div
            role="separator"
            aria-label="调整助手面板宽度"
            aria-orientation="vertical"
            aria-valuemin={MIN_CHAT_WIDTH}
            aria-valuemax={MAX_CHAT_WIDTH}
            aria-valuenow={chatWidth}
            tabIndex={0}
            onPointerDown={startResize}
            onKeyDown={resizeByKeyboard}
            onDoubleClick={() => setChatWidth(DEFAULT_CHAT_WIDTH)}
            className="group relative z-30 -ml-px hidden w-2 shrink-0 cursor-col-resize items-center justify-center outline-none focus-visible:bg-primary/10 md:flex"
          >
            <GripVertical className="h-4 w-4 text-transparent transition-colors group-hover:text-muted-foreground group-focus-visible:text-primary" />
          </div>
        )}

        <div
          className={cn(
            'relative flex min-w-0 flex-1 flex-col overflow-hidden transition-opacity duration-150',
            isCanvasOpen ? 'opacity-100' : 'w-0 flex-none opacity-0',
          )}
        >
          <TrialBanner />

          <header className="relative z-20 flex h-[3.25rem] items-center justify-between border-b bg-[hsl(var(--panel-strong)/0.96)] px-5 shadow-[0_1px_0_hsl(var(--border)/0.55)]">
            <div className="flex items-center gap-2.5">
              <span className="h-4 w-0.5 rounded-full bg-primary" aria-hidden="true" />
              <span className="text-sm font-semibold text-foreground">{getPageTitle()}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="hidden items-center rounded-md border bg-background p-0.5 lg:flex" role="group" aria-label="工作区模式">
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn('h-7 w-7', workspaceMode === 'business' && 'bg-muted text-foreground')}
                  onClick={() => setWorkspaceMode('business')}
                  aria-label="专注业务"
                  title="专注业务"
                >
                  <PanelsTopLeft className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn('h-7 w-7', workspaceMode === 'split' && 'bg-muted text-foreground')}
                  onClick={() => setWorkspaceMode('split')}
                  aria-label="并排工作"
                  title="并排工作"
                >
                  <Columns2 className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn('h-7 w-7', workspaceMode === 'assistant' && 'bg-muted text-foreground')}
                  onClick={() => setWorkspaceMode('assistant')}
                  aria-label="专注助手"
                  title="专注助手"
                >
                  <MessageSquareText className="h-3.5 w-3.5" />
                </Button>
              </div>
              {workspaceMode === 'split' && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="hidden h-8 w-8 text-muted-foreground hover:text-foreground lg:inline-flex"
                  onClick={cycleChatWidth}
                  aria-label="切换助手面板宽度"
                  title={`切换助手宽度，当前 ${chatWidth}px`}
                >
                  <PanelLeft className="h-4 w-4" />
                </Button>
              )}
              <AssistantStatusPill isChatOpen={isChatOpen} onOpen={() => setIsChatOpen(true)} />
              <NotificationCenter />
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground/60 hover:text-foreground"
                onClick={() => setIsCanvasOpen(false)}
                aria-label="隐藏业务页面"
                title="隐藏业务页面"
              >
                <PanelRightClose className="h-4 w-4" />
              </Button>
            </div>
          </header>

          <main className="workspace-canvas flex-1 overflow-y-auto p-4 md:p-6">
            <div className="mx-auto min-h-full max-w-[1600px] pb-20 xl:max-w-[1800px]">
              <div className="mb-5 opacity-80">
                <Breadcrumbs
                  items={[
                    { label: 'Nexus AI', href: '/' },
                    ...location.pathname
                      .split('/')
                      .filter(Boolean)
                      .map((segment, index, segments) => ({
                        label: segment.charAt(0).toUpperCase() + segment.slice(1),
                        href: `/${segments.slice(0, index + 1).join('/')}`,
                      })),
                  ]}
                />
              </div>
              {children || <Outlet />}
            </div>
          </main>
        </div>
      </div>

      <GlobalAIBall isOpen={isChatOpen} onClick={() => setIsChatOpen(true)} />

      {!isCanvasOpen && isPageRoute && (
        <button
          type="button"
          onClick={() => setIsCanvasOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex h-10 w-10 items-center justify-center rounded-md border bg-card text-foreground shadow-md transition-colors hover:bg-muted"
          aria-label="打开业务页面"
          title="打开业务页面"
        >
          <PanelRightOpen className="h-5 w-5" />
        </button>
      )}

      <InstallPrompt />
      <WelcomeTour />
    </div>
  );
};

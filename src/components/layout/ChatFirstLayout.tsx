import React, { useState, useCallback, useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import EnhancedAIChatPanel from '@/components/ai/EnhancedAIChatPanel';
import { Button } from '@/components/ui/button';
import { Sidebar } from '@/components/layout/Sidebar';
import { MobileSidebar } from '@/components/layout/MobileSidebar';
import { CommandPalette } from '@/components/common/CommandPalette';
import { InstallPrompt } from '@/components/common/InstallPrompt';
import { WelcomeTour } from '@/components/common/WelcomeTour';
import { NotificationCenter } from '@/components/common/NotificationCenter';
import MobileNavBar from '@/components/mobile/MobileNavBar';
import MobileHeader from '@/components/mobile/MobileHeader';
import { useIsMobile } from '@/hooks/use-mobile';
import { PanelRightClose, PanelRightOpen, ArrowLeft } from 'lucide-react';

// Interface for props
interface ChatFirstLayoutProps {
    children?: React.ReactNode;
}

export const ChatFirstLayout = ({ children }: ChatFirstLayoutProps) => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [isCanvasOpen, setIsCanvasOpen] = useState(true);
    const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
    const location = useLocation();
    const navigate = useNavigate();
    const isMobile = useIsMobile();

    // Handler for when user triggers AI chat from command palette
    const handleCommandPaletteAIChat = useCallback((message: string) => {
        // For now, this is a placeholder — could focus the chat input and prefill
        if (import.meta.env.DEV) console.log('CommandPalette AI Chat:', message);
    }, []);

    // Dynamic page title (migrated from MainLayout)
    const getPageTitle = useCallback(() => {
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
    }, [location.pathname]);

    // Map current pathname to MobileNavBar active tab id
    const getActiveTab = useCallback(() => {
        const path = location.pathname;
        if (path.includes('approval')) return 'approval';
        if (path.includes('notification-center')) return 'notifications';
        if (path.includes('profile')) return 'profile';
        if (!isCanvasOpen && (path === '/' || path === '/chat')) return 'chat';
        if (path === '/' || path.includes('dashboard')) return 'home';
        return 'home';
    }, [location.pathname]);

    // Register global keyboard shortcut: Cmd+K / Ctrl+K to open command palette
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setIsCommandPaletteOpen(true);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    // Determine if we should show the Canvas
    // If route is exactly / or /chat, we might just show chat in full screen?
    // But architecture says: Chat is Main, Pages are Canvas.

    // Check if we are on a "page" route
    const isPageRoute = location.pathname !== '/' && location.pathname !== '/chat';

    // Auto-open canvas if we are on a page route
    React.useEffect(() => {
        if (isPageRoute) {
            setIsCanvasOpen(true);
        } else {
             // Optional: Close canvas if going back to root? Or keep it?
             // Let's keep it open if user wants, but maybe default to closed on root
             // setIsCanvasOpen(false);
        }
    }, [location.pathname, isPageRoute]);

    return (
        <div className="flex h-[100dvh] w-full bg-background overflow-hidden">
            {/* 1. Navigation Sidebar (Collapsed/Icon-only by default for 'App' feel?)
                Retain existing Sidebar for now but maybe make it collapsible
            */}
             <div className="hidden md:flex h-full border-r bg-card z-20">
                <Sidebar />
            </div>

            {/* Mobile Sidebar */}
            <div className="md:hidden">
                 <MobileSidebar />
            </div>

            {/* 2. Main Work Area: Chat + Canvas Split */}
            <div className="flex flex-1 overflow-hidden relative">

                {/* A. Chat Area - The "OS" */}
                <div className={cn(
                    "flex flex-col transition-all duration-300 ease-in-out h-full relative z-10",
                    isCanvasOpen ? "w-full md:w-[45%] lg:w-[40%]" : "w-full"
                )}>
                    <EnhancedAIChatPanel
                        isExpanded={true}
                        onToggle={() => {}} // No-op in embedded mode
                        variant="embedded"
                    />

                    {/* Toggle Canvas Button (Absolute positioned on the right edge of chat) */}
                    <div className="absolute top-4 right-4 z-50 md:hidden">
                         {!isCanvasOpen && isPageRoute && (
                            <Button
                                size="icon"
                                variant="secondary"
                                className="shadow-lg rounded-full"
                                onClick={() => setIsCanvasOpen(true)}
                            >
                                <PanelRightOpen className="w-4 h-4" />
                            </Button>
                         )}
                    </div>
                </div>

                {/* B. Canvas Area - The "App" */}
                {/* On mobile, this might slide over. On Desktop, it sits side-by-side. */}
                <div className={cn(
                    "bg-background/95 backdrop-blur-sm transition-all duration-300 ease-in-out border-l shadow-2xl overflow-hidden flex flex-col",
                    // Desktop: Relative width
                    // Mobile: Absolute overlay with bottom spacing for MobileNavBar
                    isCanvasOpen ? "translate-x-0 opacity-100" : "translate-x-full opacity-0 w-0",
                    "absolute top-0 left-0 right-0 md:static md:inset-auto",
                    isMobile ? "bottom-[calc(3.5rem+env(safe-area-inset-bottom))]" : "bottom-0",
                     isCanvasOpen ? "w-full md:w-[55%] lg:w-[60%]" : "w-0"
                )}>

                   {/* Canvas Header/Controls */}
                   <div className="h-12 border-b flex items-center justify-between px-3 md:px-4 bg-card/50">
                        <div className="flex items-center gap-2">
                            {/* Mobile: show back arrow to close canvas */}
                            {isMobile && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-10 w-10 p-0 touch-manipulation"
                                    data-compact
                                    onClick={() => setIsCanvasOpen(false)}
                                    aria-label="返回对话"
                                >
                                    <ArrowLeft className="w-5 h-5" />
                                </Button>
                            )}
                            <span className="text-sm font-medium text-foreground truncate">
                                {getPageTitle()}
                            </span>
                        </div>
                        <div className="flex items-center gap-1">
                            {isMobile && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-10 w-10 p-0 touch-manipulation"
                                    data-compact
                                    onClick={() => setIsCommandPaletteOpen(true)}
                                    aria-label="搜索"
                                >
                                    <PanelRightOpen className="w-4 h-4" />
                                </Button>
                            )}
                            <NotificationCenter />
                            {!isMobile && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 w-8 p-0"
                                    data-compact
                                    onClick={() => setIsCanvasOpen(false)}
                                >
                                    <PanelRightClose className="w-4 h-4" />
                                </Button>
                            )}
                        </div>
                   </div>

                   {/* Canvas Content (Scrollable) */}
                   <div className="flex-1 overflow-auto p-2 md:p-4 custom-scrollbar pb-16 md:pb-4">
                        {children || <Outlet />}
                   </div>

                </div>

            </div>

            {/* Mobile Bottom Navigation - using the full-featured MobileNavBar */}
            {isMobile && (
                <MobileNavBar
                    activeTab={getActiveTab()}
                    onTabChange={(_tabId, path) => {
                        if (_tabId === 'chat') {
                            setIsCanvasOpen(false);
                        } else {
                            navigate(path);
                        }
                    }}
                />
            )}

            {/* Command Palette (Cmd+K / Ctrl+K) */}
            <CommandPalette
                open={isCommandPaletteOpen}
                onOpenChange={setIsCommandPaletteOpen}
                onAIChat={handleCommandPaletteAIChat}
            />

            {/* PWA Install Prompt */}
            <InstallPrompt />

            {/* Onboarding Welcome Tour */}
            <WelcomeTour />
        </div>
    );
};

import React, { useState, useCallback, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import EnhancedAIChatPanel from '@/components/ai/EnhancedAIChatPanel';
import { Button } from '@/components/ui/button';
import { Sidebar } from '@/components/layout/Sidebar';
import { InstallPrompt } from '@/components/common/InstallPrompt';
import { WelcomeTour } from '@/components/common/WelcomeTour';
import { NotificationCenter } from '@/components/common/NotificationCenter';
import { PanelRightClose, PanelRightOpen, Clock } from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { TrialBanner } from '@/components/billing/TrialBanner';
import { useWebSocketPush } from '@/hooks/useWebSocketPush';
import { Breadcrumbs } from './Breadcrumbs';
import { GlobalAIBall } from '@/components/ai/GlobalAIBall';

interface ChatFirstLayoutProps {
    children?: React.ReactNode;
}

export const ChatFirstLayout = ({ children }: ChatFirstLayoutProps) => {
    const [isCanvasOpen, setIsCanvasOpen] = useState(true);
    const [isChatOpen, setIsChatOpen] = useState(true);
    const location = useLocation();
    const { isPendingBoss } = useAuth();

    useWebSocketPush();

    const getPageTitle = useCallback(() => {
        const path = location.pathname;
        if (path.includes('boss-dashboard')) return '总控中心';
        if (path.includes('performance-dashboard')) return '战绩看板';
        if (path.includes('dashboard')) return '行动台';
        if (path.includes('workbench')) return '工作台';
        if (path.includes('ai-center')) return 'AI 中心';
        if (path.includes('data')) return '数据';
        if (path.includes('crm')) return 'CRM';
        if (path.includes('sales')) return '销售管道';
        if (path.includes('projects')) return '项目管理';
        if (path.includes('approval')) return '智能审批';
        if (path.includes('knowledge')) return '知识库';
        if (path.includes('vmd')) return '虚拟市场部';
        if (path.includes('org-chart')) return '组织架构';
        if (path.includes('settings')) return '系统设置';
        return 'Nexus OS';
    }, [location.pathname]);

    const isPageRoute = location.pathname !== '/' && location.pathname !== '/chat';

    React.useEffect(() => {
        if (isPageRoute) setIsCanvasOpen(true);
    }, [location.pathname, isPageRoute]);

    useEffect(() => {
        const handler = () => setIsChatOpen(true);
        window.addEventListener('proactive-chat', handler);
        return () => window.removeEventListener('proactive-chat', handler);
    }, []);

    return (
        <div className="flex h-[100dvh] w-full bg-background overflow-hidden text-foreground">
            {isPendingBoss && (
                <div className="fixed top-0 left-0 right-0 z-50 bg-warning text-warning-foreground text-center text-xs py-2 px-4 backdrop-blur-md flex items-center justify-center gap-2">
                    <Clock className="w-3.5 h-3.5" />
                    账号审核中 · 您目前以普通员工身份模式运行
                </div>
            )}

            {/* Sidebar with Abyss contrast */}
            <div className={cn("hidden md:flex h-full z-20 relative border-r border-border", isPendingBoss && "pt-9")}>
                <Sidebar />
            </div>

            {/* Main Content Area */}
            <div className="flex flex-1 overflow-hidden relative">
                {/* Chat Panel - Glassy and subtle */}
                <div className={cn(
                    "flex flex-col transition-all duration-500 ease-out-expo h-full relative z-10 border-r border-border",
                    isChatOpen ? (isCanvasOpen ? "w-[45%] lg:w-[38%] xl:w-[35%]" : "w-full") : "w-0 overflow-hidden opacity-0"
                )}>
                    <EnhancedAIChatPanel
                        isExpanded={isChatOpen}
                        onToggle={() => setIsChatOpen(!isChatOpen)}
                        variant="embedded"
                    />
                </div>

                {/* Canvas Area - Bento Styled */}
                <div className={cn(
                    "transition-all duration-500 ease-out-expo overflow-hidden flex flex-col relative",
                    isCanvasOpen ? "translate-x-0 opacity-100" : "translate-x-full opacity-0 w-0",
                    isCanvasOpen ? (isChatOpen ? "w-[55%] lg:w-[62%] xl:w-[65%]" : "w-full flex-1") : "w-0"
                )}>
                    {/* Trial Banner */}
                    <TrialBanner />

                    {/* Floating Header */}
                    <header className="h-14 flex items-center justify-between px-6 bg-card/10 backdrop-blur-md border-b border-border/10 relative z-20">
                        <div className="flex items-center gap-3">
                            <div className="h-2 w-2 rounded-full bg-primary/40 animate-pulse" />
                            <span className="text-caption font-semibold uppercase tracking-[0.15em] text-muted-foreground/80">
                                {getPageTitle()}
                            </span>
                        </div>
                        <div className="flex items-center gap-3">
                            <NotificationCenter />
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-muted-foreground/60 hover:text-foreground"
                                onClick={() => setIsCanvasOpen(false)}
                            >
                                <PanelRightClose className="w-4 h-4" />
                            </Button>
                        </div>
                    </header>

                    {/* Scrollable Content with Staggered Entrance Container */}
                    <main className="flex-1 overflow-y-auto no-scrollbar p-6 bg-background">
                        <div className="max-w-[1600px] xl:max-w-[1800px] mx-auto min-h-full pb-20">
                            <div className="mb-6 opacity-70">
                                <Breadcrumbs items={[
                                    { label: 'Nexus AI', href: '/' },
                                    ...location.pathname.split('/').filter(Boolean).map((segment, idx, arr) => ({
                                        label: segment.charAt(0).toUpperCase() + segment.slice(1),
                                        href: '/' + arr.slice(0, idx + 1).join('/')
                                    }))
                                ]} />
                            </div>
                            {children || <Outlet />}
                        </div>
                    </main>
                </div>
            </div>

            {/* Float Triggers */}
            {/* Global AI Magic Ball Trigger */}
            <GlobalAIBall 
                isOpen={isChatOpen} 
                onClick={() => setIsChatOpen(true)} 
            />

            {!isCanvasOpen && isPageRoute && (
                <button
                    onClick={() => setIsCanvasOpen(true)}
                    className="fixed bottom-8 right-8 z-50 w-12 h-12 bg-card border border-border rounded-2xl shadow-2xl flex items-center justify-center text-foreground hover:scale-110 active:scale-95 transition-all"
                >
                    <PanelRightOpen className="w-6 h-6" />
                </button>
            )}

            <InstallPrompt />
            <WelcomeTour />
        </div>
    );
};

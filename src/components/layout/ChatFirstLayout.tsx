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
            <span className={cn("h-1.5 w-1.5 rounded-full", isWorking ? "bg-primary" : "bg-muted-foreground/50")} />
            <span>{isWorking ? '助手正在整理请求' : isChatOpen ? '助手已开启' : '助手待命'}</span>
        </button>
    );
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
        if (path.includes('dashboard')) return '收件箱';
        if (path.includes('workbench')) return '工作台';
        if (path.includes('ai-center')) return '助手';
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
                <div className="fixed left-0 right-0 top-0 z-50 flex items-center justify-center gap-2 bg-warning px-4 py-2 text-center text-xs text-warning-foreground">
                    <Clock className="w-3.5 h-3.5" />
                    账号审核中 · 您目前以普通员工身份模式运行
                </div>
            )}

            {/* Stable enterprise navigation rail */}
            <div className={cn("hidden md:flex h-full z-20 relative border-r border-border", isPendingBoss && "pt-9")}>
                <Sidebar />
            </div>

            {/* Main Content Area */}
            <div className="flex flex-1 overflow-hidden relative">
                {/* Assistant panel uses a stable tool width. */}
                <div className={cn(
                    "flex h-full flex-col border-r border-border bg-card transition-[width,opacity] duration-200",
                    isChatOpen ? (isCanvasOpen ? "w-[400px] max-w-[42vw]" : "w-full") : "w-0 overflow-hidden opacity-0"
                )}>
                    <EnhancedAIChatPanel
                        isExpanded={isChatOpen}
                        onToggle={() => setIsChatOpen(!isChatOpen)}
                        variant="embedded"
                    />
                </div>

                {/* Primary work surface */}
                <div className={cn(
                    "relative flex min-w-0 flex-1 flex-col overflow-hidden transition-opacity duration-150",
                    isCanvasOpen ? "opacity-100" : "w-0 flex-none opacity-0"
                )}>
                    {/* Trial Banner */}
                    <TrialBanner />

                    <header className="relative z-20 flex h-12 items-center justify-between border-b bg-card px-5">
                        <div className="flex items-center gap-3">
                            <span className="text-sm font-medium text-foreground">
                                {getPageTitle()}
                            </span>
                        </div>
                        <div className="flex items-center gap-3">
                            <AssistantStatusPill isChatOpen={isChatOpen} onOpen={() => setIsChatOpen(true)} />
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

                    <main className="flex-1 overflow-y-auto bg-background p-4 md:p-5">
                        <div className="max-w-[1600px] xl:max-w-[1800px] mx-auto min-h-full pb-20">
                            <div className="mb-4">
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
                    className="fixed bottom-6 right-6 z-50 flex h-10 w-10 items-center justify-center rounded-md border bg-card text-foreground shadow-md transition-colors hover:bg-muted"
                >
                    <PanelRightOpen className="w-6 h-6" />
                </button>
            )}

            <InstallPrompt />
            <WelcomeTour />
        </div>
    );
};

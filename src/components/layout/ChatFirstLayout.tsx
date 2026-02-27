import React, { useState, useCallback } from 'react';
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

// Interface for props
interface ChatFirstLayoutProps {
    children?: React.ReactNode;
}

/**
 * 桌面端 Layout：左 Chat + 右 Canvas 双栏布局
 * 移动端已迁移到 MobileLayout，此组件仅服务桌面端 (≥768px)
 */
export const ChatFirstLayout = ({ children }: ChatFirstLayoutProps) => {
    const [isCanvasOpen, setIsCanvasOpen] = useState(true);
    const location = useLocation();
    const { isPendingBoss } = useAuth();

    // Dynamic page title
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
        if (path.includes('vmd/tasks')) return '任务中心';
        if (path.includes('vmd/agents')) return 'Agent配置';
        if (path.includes('vmd/clues')) return '线索管理';
        if (path.includes('vmd/compliance')) return '合规校验';
        if (path.includes('vmd/dashboard')) return '数据看板';
        if (path.includes('vmd')) return '虚拟市场部';
        if (path.includes('org-chart')) return '组织架构';
        if (path.includes('llm/models')) return '模型管理';
        if (path.includes('agent-debug')) return 'Agent 调试面板';
        return 'Nexus OS';
    }, [location.pathname]);

    // Auto-open canvas on page routes
    const isPageRoute = location.pathname !== '/' && location.pathname !== '/chat';

    React.useEffect(() => {
        if (isPageRoute) {
            setIsCanvasOpen(true);
        }
    }, [location.pathname, isPageRoute]);

    return (
        <div className="flex h-[100dvh] w-full bg-background overflow-hidden">
            {/* Pending Boss Banner */}
            {isPendingBoss && (
                <div className="fixed top-0 left-0 right-0 z-50 bg-amber-500/90 text-white text-center text-sm py-2 px-4 flex items-center justify-center gap-2">
                    <Clock className="w-4 h-4" />
                    您的管理员账号正在审核中，审核通过前可以普通员工身份使用系统
                </div>
            )}

            {/* Sidebar */}
            <div className={cn("flex h-full border-r bg-card z-20", isPendingBoss && "pt-9")}>
                <Sidebar />
            </div>

            {/* Main Work Area: Chat + Canvas Split */}
            <div className="flex flex-1 overflow-hidden relative">

                {/* Chat Area */}
                <div className={cn(
                    "flex flex-col transition-all duration-300 ease-in-out h-full relative z-10",
                    isCanvasOpen ? "w-[45%] lg:w-[40%]" : "w-full"
                )}>
                    <EnhancedAIChatPanel
                        isExpanded={true}
                        onToggle={() => {}}
                        variant="embedded"
                    />
                </div>

                {/* Canvas Area */}
                <div className={cn(
                    "bg-background/95 backdrop-blur-sm transition-all duration-300 ease-in-out border-l shadow-2xl overflow-hidden flex flex-col",
                    isCanvasOpen ? "translate-x-0 opacity-100" : "translate-x-full opacity-0 w-0",
                    "static inset-auto bottom-0",
                    isCanvasOpen ? "w-[55%] lg:w-[60%]" : "w-0"
                )}>

                   {/* Canvas Header */}
                   <div className="h-12 border-b flex items-center justify-between px-4 bg-card/50">
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-foreground truncate">
                                {getPageTitle()}
                            </span>
                        </div>
                        <div className="flex items-center gap-1">
                            <NotificationCenter />
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0"
                                data-compact
                                onClick={() => setIsCanvasOpen(false)}
                            >
                                <PanelRightClose className="w-4 h-4" />
                            </Button>
                        </div>
                   </div>

                   {/* Canvas Content */}
                   <div className="flex-1 overflow-auto p-2 md:p-4 custom-scrollbar pb-4 relative">
                        {children || <Outlet />}
                   </div>

                </div>

            </div>

            {/* Canvas reopen button when closed */}
            {!isCanvasOpen && isPageRoute && (
                <Button
                    size="icon"
                    variant="secondary"
                    className="fixed top-4 right-4 z-50 shadow-lg rounded-full"
                    onClick={() => setIsCanvasOpen(true)}
                >
                    <PanelRightOpen className="w-4 h-4" />
                </Button>
            )}

            {/* PWA Install Prompt */}
            <InstallPrompt />

            {/* Onboarding Welcome Tour */}
            <WelcomeTour />
        </div>
    );
};

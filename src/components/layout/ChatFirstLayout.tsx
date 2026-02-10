import React, { useState, useCallback } from 'react';
import { Outlet, Navigate, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import EnhancedAIChatPanel from '@/components/ai/EnhancedAIChatPanel';
import { Button } from '@/components/ui/button';
import { Sidebar } from '@/components/layout/Sidebar';
import { MobileSidebar } from '@/components/layout/MobileSidebar';
import { CommandPalette } from '@/components/common/CommandPalette';
import { PanelRightClose, PanelRightOpen, Menu } from 'lucide-react';

// Interface for props
interface ChatFirstLayoutProps {
    children?: React.ReactNode;
}

export const ChatFirstLayout = ({ children }: ChatFirstLayoutProps) => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [isCanvasOpen, setIsCanvasOpen] = useState(true);
    const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
    const location = useLocation();

    // Handler for when user triggers AI chat from command palette
    const handleCommandPaletteAIChat = useCallback((message: string) => {
        // For now, this is a placeholder — could focus the chat input and prefill
        console.log('CommandPalette AI Chat:', message);
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
        <div className="flex h-screen w-full bg-background overflow-hidden">
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
                    // Mobile: Absolute overlay?
                    isCanvasOpen ? "translate-x-0 opacity-100" : "translate-x-full opacity-0 w-0",
                    "absolute inset-0 md:static md:inset-auto", // Mobile overlay
                     isCanvasOpen ? "w-full md:w-[55%] lg:w-[60%]" : "w-0"
                )}>
                   
                   {/* Canvas Header/Controls */}
                   <div className="h-12 border-b flex items-center justify-between px-4 bg-card/50">
                        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                            Workspace
                        </span>
                        <div className="flex items-center gap-2">
                             <Button 
                                variant="ghost" 
                                size="sm" 
                                className="h-8 w-8 p-0" 
                                onClick={() => setIsCanvasOpen(false)}
                            >
                                <PanelRightClose className="w-4 h-4" />
                            </Button>
                        </div>
                   </div>

                   {/* Canvas Content (Scrollable) */}
                   <div className="flex-1 overflow-auto bg-muted/10 p-4 md:p-6 custom-scrollbar">
                        <div className="max-w-6xl mx-auto min-h-full bg-card rounded-xl border shadow-sm p-4 md:p-8">
                             {children || <Outlet />}
                        </div>
                   </div>

                </div>

            </div>
                    {/* Command Palette (⌘K) */}
            <CommandPalette
                open={isCommandPaletteOpen}
                onOpenChange={setIsCommandPaletteOpen}
                onAIChat={handleCommandPaletteAIChat}
            />
        </div>
    );
};

import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { ActiveCardStream } from '../cards/ActiveCardStream';
import { AIChatPanel } from '../ai/AIChatPanel';
import { useUser } from '@/contexts/UserContext';

interface MainLayoutProps {
  children: React.ReactNode;
  activeNav: string;
  onNavChange: (nav: string) => void;
}

export function MainLayout({ children, activeNav, onNavChange }: MainLayoutProps) {
  const { user } = useUser();
  const [isChatExpanded, setIsChatExpanded] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar activeNav={activeNav} onNavChange={onNavChange} />
      
      {/* Main Content Area */}
      <div className="ml-64 mr-80 min-h-screen">
        <main className="p-6">
          {children}
        </main>
      </div>

      {/* Right Panel - Active Cards Stream */}
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

      {/* Bottom AI Chat Panel */}
      <AIChatPanel 
        isExpanded={isChatExpanded} 
        onToggle={() => setIsChatExpanded(!isChatExpanded)} 
      />
    </div>
  );
}

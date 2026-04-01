import React from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { UserProvider } from '@/contexts/UserContext';
import { ChatFirstLayout } from '@/components/layout/ChatFirstLayout';
import { MobileLayout } from '@/components/layout/MobileLayout';
import { useIsMobile, useIsTablet } from '@/hooks/use-mobile';
import { Outlet } from 'react-router-dom';
import { SkipToContent } from '@/components/common/SkipToContent';
import { GlobalHotkeys } from '@/components/common/GlobalHotkeys';

const Index = () => {
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();

  return (
    <ThemeProvider>
      <UserProvider>
        <SkipToContent />
        <GlobalHotkeys />
        {(isMobile || isTablet) ? (
          <MobileLayout />
        ) : (
          <ChatFirstLayout>
            <main id="main-content">
              <Outlet />
            </main>
          </ChatFirstLayout>
        )}
      </UserProvider>
    </ThemeProvider>
  );
};

export default Index;

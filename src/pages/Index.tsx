import React from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { UserProvider } from '@/contexts/UserContext';
import { ChatFirstLayout } from '@/components/layout/ChatFirstLayout';
import { MobileLayout } from '@/components/layout/MobileLayout';
import { useIsMobile } from '@/hooks/use-mobile';
import { Outlet } from 'react-router-dom';

const Index = () => {
  const isMobile = useIsMobile();

  return (
    <ThemeProvider>
      <UserProvider>
        {isMobile ? (
          <MobileLayout />
        ) : (
          <ChatFirstLayout>
            <Outlet />
          </ChatFirstLayout>
        )}
      </UserProvider>
    </ThemeProvider>
  );
};

export default Index;

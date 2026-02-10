import React from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { UserProvider } from '@/contexts/UserContext';
import { ChatFirstLayout } from '@/components/layout/ChatFirstLayout';
import { Outlet } from 'react-router-dom';

const Index = () => {
  return (
    <ThemeProvider>
      <UserProvider>
        <ChatFirstLayout>
          <Outlet />
        </ChatFirstLayout>
      </UserProvider>
    </ThemeProvider>
  );
};

export default Index;

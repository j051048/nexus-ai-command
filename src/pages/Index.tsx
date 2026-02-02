import React from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { UserProvider } from '@/contexts/UserContext';
import { MainLayout } from '@/components/layout/MainLayout';
import { Outlet } from 'react-router-dom';

const Index = () => {
  return (
    <ThemeProvider>
      <UserProvider>
        <MainLayout>
          <Outlet />
        </MainLayout>
      </UserProvider>
    </ThemeProvider>
  );
};

export default Index;

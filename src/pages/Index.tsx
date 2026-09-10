import React from 'react';
import { UserProvider } from '@/contexts/UserContext';
import { ChatFirstLayout } from '@/components/layout/ChatFirstLayout';
import { MobileLayout } from '@/components/layout/MobileLayout';
import { useIsMobile, useIsTablet } from '@/hooks/use-mobile';
import { Outlet } from 'react-router-dom';
import { SkipToContent } from '@/components/common/SkipToContent';
import { GlobalHotkeys } from '@/components/common/GlobalHotkeys';
import { DeliverableWorkspace } from '@/components/deliverables/DeliverableWorkspace';

const Index = () => {
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();

  return (
    <UserProvider>
      <SkipToContent />
      <GlobalHotkeys />
      <DeliverableWorkspace compact={isMobile || isTablet}>
        {(deliverablesAction) => (isMobile || isTablet) ? (
          <MobileLayout deliverablesAction={deliverablesAction} />
        ) : (
          <ChatFirstLayout deliverablesAction={deliverablesAction}>
            <main id="main-content">
              <Outlet />
            </main>
          </ChatFirstLayout>
        )}
      </DeliverableWorkspace>
    </UserProvider>
  );
};

export default Index;

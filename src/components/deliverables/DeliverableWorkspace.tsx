import { useRef, useState, type ReactNode } from 'react';
import { useAuth } from '@/components/auth/AuthContext';
import { DeliverableCenter } from './DeliverableCenter';
import { DeliverableCenterTrigger } from './DeliverableCenterTrigger';

interface WorkspaceProps {
  compact: boolean;
  children: (trigger: ReactNode) => ReactNode;
}

function ScopedWorkspace({ compact, children }: WorkspaceProps) {
  const [open, setOpen] = useState(false);
  const [recentCount, setRecentCount] = useState(0);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // The headers may remount on rotation; the document and unsent edits must not.
  return <>
    {children(<DeliverableCenterTrigger ref={triggerRef} iconOnly={compact} recentCount={recentCount} onClick={() => setOpen(true)} />)}
    <DeliverableCenter
      open={open}
      onOpenChange={setOpen}
      showTrigger={false}
      onRecentCountChange={setRecentCount}
      returnFocusRef={triggerRef}
    />
  </>;
}

export function DeliverableWorkspace(props: WorkspaceProps) {
  const { profile, user } = useAuth();
  const identity = JSON.stringify([profile?.organization_id, user?.id]);
  // Never carry a preview or a revision draft across an account/tenant switch.
  return <ScopedWorkspace key={identity} {...props} />;
}

import React from 'react';
import { Navigate } from 'react-router-dom';
import { MembershipGate } from '@/components/billing/MembershipGate';
import { isModuleEnabled, type ModuleFlag } from '@/config/featureFlags';

type ModuleGateProps = {
  flag: ModuleFlag;
  children: React.ReactNode;
};

export function ModuleGate({ flag, children }: ModuleGateProps) {
  if (!isModuleEnabled(flag)) {
    return <Navigate to="/dashboard" replace />;
  }
  if (flag === 'billing') {
    return <>{children}</>;
  }
  return <MembershipGate>{children}</MembershipGate>;
}

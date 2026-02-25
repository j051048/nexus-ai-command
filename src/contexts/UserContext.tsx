/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect, useMemo, useCallback, ReactNode } from 'react';
import { useAuth } from '@/components/auth/AuthContext';
import { Badge, UserRole } from '@/types/nexus';

interface User {
  id: string;
  name: string;
  avatar: string;
  role: UserRole;
  department: string;
  score: number;
  rank: number;
  totalBonus: number;
  badges: Badge[];
  employeeNumber: string | null;
  jobTitle: string | null;
}

interface UserContextType {
  user: User;
  setRole: (role: UserRole) => void;
  addBonus: (amount: number) => void;
  updateScore: (delta: number) => void;
}

const defaultBadges: Badge[] = [];

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const { profile, role: authRole } = useAuth();

  const [user, setUser] = useState<User>({
    id: profile?.id || '1',
    name: profile?.name || '用户',
    avatar: profile?.avatar || '',
    role: authRole || 'employee',
    department: profile?.department || '销售部',
    score: profile?.score ?? 0,
    rank: profile?.rank ?? 0,
    totalBonus: Number(profile?.total_bonus) || 0,
    badges: defaultBadges,
    employeeNumber: profile?.employee_number || null,
    jobTitle: profile?.job_title || null,
  });

  // Sync with auth profile when it changes
  useEffect(() => {
    if (profile) {
      setUser(prev => ({
        ...prev,
        id: profile.id,
        name: profile.name,
        avatar: profile.avatar || '',
        department: profile.department || '销售部',
        score: profile.score ?? 0,
        rank: profile.rank ?? 0,
        totalBonus: Number(profile.total_bonus) || 0,
        employeeNumber: profile.employee_number || null,
        jobTitle: profile.job_title || null,
      }));
    }
  }, [profile]);

  // Sync role from auth
  useEffect(() => {
    if (authRole) {
      setUser(prev => ({ ...prev, role: authRole }));
    }
  }, [authRole]);

  const setRole = useCallback((role: UserRole) => {
    setUser(prev => ({ ...prev, role }));
  }, []);

  const addBonus = useCallback((amount: number) => {
    setUser(prev => ({
      ...prev,
      totalBonus: prev.totalBonus + amount,
    }));
  }, []);

  const updateScore = useCallback((delta: number) => {
    setUser(prev => ({
      ...prev,
      score: Math.min(100, Math.max(0, prev.score + delta)),
    }));
  }, []);

  const value = useMemo(() => ({ user, setRole, addBonus, updateScore }), [user, setRole, addBonus, updateScore]);

  return (
    <UserContext.Provider value={value}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
}

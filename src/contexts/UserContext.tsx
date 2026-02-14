/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
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
}

interface UserContextType {
  user: User;
  setRole: (role: UserRole) => void;
  addBonus: (amount: number) => void;
  updateScore: (delta: number) => void;
}

const defaultBadges: Badge[] = [
  { id: '1', name: '学术猎手', icon: '🎯', description: '成功转化3位教授客户', tier: 'gold', unlockedAt: new Date() },
  { id: '2', name: '话术大师', icon: '💬', description: 'AI通话评分连续5次90+', tier: 'silver', unlockedAt: new Date() },
  { id: '3', name: '速战速决', icon: '⚡', description: '平均响应时间<2小时', tier: 'bronze', unlockedAt: new Date() },
];

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const { profile, role: authRole } = useAuth();

  const [user, setUser] = useState<User>({
    id: profile?.id || '1',
    name: profile?.name || '用户',
    avatar: profile?.avatar || '',
    role: authRole || 'employee',
    department: profile?.department || '销售部',
    score: profile?.score || 87,
    rank: profile?.rank || 3,
    totalBonus: Number(profile?.total_bonus) || 4850,
    badges: defaultBadges,
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
        score: profile.score || 87,
        rank: profile.rank || 3,
        totalBonus: Number(profile.total_bonus) || 4850,
      }));
    }
  }, [profile]);

  // Sync role from auth
  useEffect(() => {
    if (authRole) {
      setUser(prev => ({ ...prev, role: authRole }));
    }
  }, [authRole]);

  const setRole = (role: UserRole) => {
    setUser(prev => ({ ...prev, role }));
  };

  const addBonus = (amount: number) => {
    setUser(prev => ({
      ...prev,
      totalBonus: prev.totalBonus + amount,
    }));
  };

  const updateScore = (delta: number) => {
    setUser(prev => ({
      ...prev,
      score: Math.min(100, Math.max(0, prev.score + delta)),
    }));
  };

  return (
    <UserContext.Provider value={{ user, setRole, addBonus, updateScore }}>
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

import React, { createContext, useContext, useState, ReactNode } from 'react';
import { User, UserRole, Badge } from '@/types/nexus';

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

const defaultUser: User = {
  id: '1',
  name: '张明',
  avatar: '',
  role: 'employee',
  department: '销售部',
  score: 87,
  rank: 3,
  totalBonus: 4850,
  badges: defaultBadges,
};

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User>(defaultUser);

  const setRole = (role: UserRole) => {
    setUser(prev => ({
      ...prev,
      role,
      name: role === 'boss' ? '李总' : '张明',
    }));
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

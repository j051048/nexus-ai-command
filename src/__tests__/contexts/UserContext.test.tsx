import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';

// Mock AuthContext
const mockProfile = {
  id: 'user-001',
  name: '张三',
  avatar: 'https://example.com/avatar.jpg',
  department: '技术部',
  score: 75,
  rank: 3,
  total_bonus: 5000,
  employee_number: 'EMP001',
  job_title: '高级工程师',
};

let mockAuthRole = 'employee';

vi.mock('@/components/auth/AuthContext', () => ({
  useAuth: () => ({
    profile: mockProfile,
    role: mockAuthRole,
  }),
}));

// Mock types
vi.mock('@/types/nexus', () => ({
  // Badge 类型只需要提供空的类型定义
}));

import { UserProvider, useUser } from '@/contexts/UserContext';

function wrapper({ children }: { children: React.ReactNode }) {
  return React.createElement(UserProvider, null, children);
}

describe('UserContext', () => {
  beforeEach(() => {
    mockAuthRole = 'employee';
  });

  it('应从 AuthContext 同步 profile 数据', () => {
    const { result } = renderHook(() => useUser(), { wrapper });

    expect(result.current.user.id).toBe('user-001');
    expect(result.current.user.name).toBe('张三');
    expect(result.current.user.department).toBe('技术部');
    expect(result.current.user.score).toBe(75);
    expect(result.current.user.totalBonus).toBe(5000);
    expect(result.current.user.employeeNumber).toBe('EMP001');
    expect(result.current.user.jobTitle).toBe('高级工程师');
  });

  it('setRole 应正确切换角色', () => {
    const { result } = renderHook(() => useUser(), { wrapper });

    act(() => {
      result.current.setRole('manager');
    });

    expect(result.current.user.role).toBe('manager');
  });

  it('addBonus 应正确累加奖金', () => {
    const { result } = renderHook(() => useUser(), { wrapper });

    const initialBonus = result.current.user.totalBonus;

    act(() => {
      result.current.addBonus(1000);
    });

    expect(result.current.user.totalBonus).toBe(initialBonus + 1000);

    act(() => {
      result.current.addBonus(500);
    });

    expect(result.current.user.totalBonus).toBe(initialBonus + 1500);
  });

  it('updateScore 应正确更新分数', () => {
    const { result } = renderHook(() => useUser(), { wrapper });

    act(() => {
      result.current.updateScore(10);
    });

    expect(result.current.user.score).toBe(85); // 75 + 10
  });

  it('updateScore 应 clamp 到 0-100 范围 (上限)', () => {
    const { result } = renderHook(() => useUser(), { wrapper });

    act(() => {
      result.current.updateScore(50); // 75 + 50 = 125 → clamp to 100
    });

    expect(result.current.user.score).toBe(100);
  });

  it('updateScore 应 clamp 到 0-100 范围 (下限)', () => {
    const { result } = renderHook(() => useUser(), { wrapper });

    act(() => {
      result.current.updateScore(-200); // 75 - 200 = -125 → clamp to 0
    });

    expect(result.current.user.score).toBe(0);
  });

  it('useUser 在 Provider 外使用应抛出错误', () => {
    // 不使用 wrapper
    expect(() => {
      renderHook(() => useUser());
    }).toThrow('useUser must be used within a UserProvider');
  });
});

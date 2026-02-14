/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';

// ─── Mock localStorage ──────────────────────────────────────

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// ─── 测试用例 ──────────────────────────────────────────────

describe('InstallPrompt', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.clear();
    // 确保 matchMedia 返回 false (非 standalone 模式)
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    });
  });

  it('初始状态不可见（需要等 beforeinstallprompt 事件）', async () => {
    const { InstallPrompt } = await import('@/components/common/InstallPrompt');
    const { container } = render(<InstallPrompt />);

    // 组件初始不可见（等待 beforeinstallprompt 事件）
    expect(container.innerHTML).toBe('');
  });

  it('beforeinstallprompt 事件触发后显示安装提示', async () => {
    const { InstallPrompt } = await import('@/components/common/InstallPrompt');
    render(<InstallPrompt />);

    // 模拟 beforeinstallprompt 事件
    const event = new Event('beforeinstallprompt', { cancelable: true });
    (event as any).prompt = vi.fn().mockResolvedValue(undefined);
    (event as any).userChoice = Promise.resolve({ outcome: 'accepted' as const });

    await act(async () => {
      window.dispatchEvent(event);
    });

    expect(screen.getByText('安装 Nexus AI 到桌面')).toBeInTheDocument();
    expect(screen.getByText('安装')).toBeInTheDocument();
  });

  it('关闭后在 localStorage 标记已处理', async () => {
    const { InstallPrompt } = await import('@/components/common/InstallPrompt');
    render(<InstallPrompt />);

    // 触发 beforeinstallprompt
    const event = new Event('beforeinstallprompt', { cancelable: true });
    (event as any).prompt = vi.fn().mockResolvedValue(undefined);
    (event as any).userChoice = Promise.resolve({ outcome: 'dismissed' as const });

    await act(async () => {
      window.dispatchEvent(event);
    });

    // 点击关闭
    const closeButton = screen.getByLabelText('关闭安装提示');
    await act(async () => {
      fireEvent.click(closeButton);
    });

    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      'nexus-pwa-install-dismissed',
      'dismissed',
    );
  });

  it('已被 dismissed 后不再显示', async () => {
    localStorageMock.getItem.mockReturnValue('dismissed');

    const { InstallPrompt } = await import('@/components/common/InstallPrompt');
    const { container } = render(<InstallPrompt />);

    // 触发 beforeinstallprompt
    const event = new Event('beforeinstallprompt', { cancelable: true });
    await act(async () => {
      window.dispatchEvent(event);
    });

    // 组件应该不渲染内容
    expect(container.innerHTML).toBe('');
  });
});

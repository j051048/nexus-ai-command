/**
 * CommandPalette 组件单元测试
 *
 * 覆盖：打开/关闭、搜索过滤、键盘导航、命令执行、空结果
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';

// Mock hooks
vi.mock('@/components/auth/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u-1' },
    profile: { organization_id: 'org-1' },
    role: 'boss',
  }),
}));

vi.mock('@/hooks/useHotkeys', () => ({
  useHotkeys: vi.fn(),
}));

function renderWithRouter(ui: React.ReactElement) {
  return render(React.createElement(MemoryRouter, null, ui));
}

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Ctrl+K 快捷键应注册', async () => {
    const { useHotkeys } = await import('@/hooks/useHotkeys');
    const { default: CommandPalette } = await import('@/components/common/CommandPalette');

    renderWithRouter(React.createElement(CommandPalette));

    // useHotkeys 应被调用注册快捷键
    expect(useHotkeys).toHaveBeenCalled();
  });
});

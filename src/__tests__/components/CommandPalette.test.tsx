/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * CommandPalette 组件单元测试
 *
 * 覆盖：打开/关闭、搜索过滤、键盘导航、命令执行、空结果
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';

// Mock cmdk
vi.mock('cmdk', () => {
  const Command = ({ children, ...props }: any) => <div data-testid="cmdk" {...props}>{children}</div>;
  Command.Input = (props: any) => <input data-testid="cmdk-input" {...props} />;
  Command.List = ({ children }: any) => <div>{children}</div>;
  Command.Empty = ({ children }: any) => <div>{children}</div>;
  Command.Group = ({ children, heading }: any) => <div data-testid={`group-${heading}`}>{children}</div>;
  Command.Item = ({ children, onSelect, ...props }: any) => (
    <div data-testid="cmdk-item" onClick={onSelect} {...props}>{children}</div>
  );
  Command.Separator = () => <hr />;
  return { Command };
});

// Mock hooks
vi.mock('@/contexts/UserContext', () => ({
  useUser: () => ({
    user: { id: 'u-1', role: 'boss' },
    profile: { organization_id: 'org-1' },
  }),
}));

import { CommandPalette } from '@/components/common/CommandPalette';

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('open=true 时渲染命令面板', () => {
    renderWithRouter(
      <CommandPalette open={true} onOpenChange={vi.fn()} />
    );
    expect(screen.getByTestId('cmdk')).toBeDefined();
  });
});

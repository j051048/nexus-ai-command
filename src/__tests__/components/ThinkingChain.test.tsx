/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * ThinkingChain 组件单元测试
 *
 * 覆盖：各阶段渲染、展开/折叠工具详情、流式动画、空步骤、完成状态
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: React.forwardRef(({ children, ...props }: any, ref: any) =>
      React.createElement('div', { ...props, ref }, children)
    ),
  },
  AnimatePresence: ({ children }: any) => React.createElement(React.Fragment, null, children),
}));

import { default as ThinkingChain } from '@/components/ai/ThinkingChain';
import type { ThinkingStep } from '@/components/ai/ThinkingChain';

const baseSteps: ThinkingStep[] = [
  {
    phase: 'planning',
    content: '分析用户意图，准备查询客户数据',
    timestamp: Date.now(),
  },
  {
    phase: 'executing',
    content: '调用 CRM 工具获取客户列表',
    tool_name: 'GetCustomersTool',
    tool_args: { limit: 10 },
    tool_result: '找到 5 个客户',
    timestamp: Date.now(),
    duration_ms: 230,
  },
  {
    phase: 'reflecting',
    content: '验证数据完整性',
    timestamp: Date.now(),
  },
  {
    phase: 'responding',
    content: '生成最终回复',
    timestamp: Date.now(),
  },
];

describe('ThinkingChain', () => {
  it('渲染所有阶段标签', () => {
    render(React.createElement(ThinkingChain, { steps: baseSteps }));
    // 折叠状态下 badge 显示 label 或 tool_name
    expect(screen.getByText(/规划/)).toBeInTheDocument();
    expect(screen.getByText(/GetCustomersTool/)).toBeInTheDocument(); // executing badge shows tool_name
    expect(screen.getByText(/反思/)).toBeInTheDocument();
    expect(screen.getByText(/回复/)).toBeInTheDocument();
  });

  it('折叠状态显示工具名和耗时', () => {
    render(React.createElement(ThinkingChain, { steps: baseSteps }));
    // 折叠状态下 badge 显示 tool_name 和 duration
    expect(screen.getByText(/GetCustomersTool/)).toBeInTheDocument();
    expect(screen.getByText(/230ms/)).toBeInTheDocument();
  });

  it('展开后显示步骤内容文本', () => {
    render(React.createElement(ThinkingChain, { steps: baseSteps }));
    // 点击 header 展开
    fireEvent.click(screen.getByText('思考过程'));
    expect(screen.getByText('分析用户意图，准备查询客户数据')).toBeInTheDocument();
    expect(screen.getByText('调用 CRM 工具获取客户列表')).toBeInTheDocument();
  });

  it('展开后点击工具步骤显示详情', () => {
    render(React.createElement(ThinkingChain, { steps: baseSteps }));
    // 先展开整个链
    fireEvent.click(screen.getByText('思考过程'));
    // 点击执行步骤展开工具详情
    const execLabel = screen.getByText('执行');
    fireEvent.click(execLabel.closest('[class*="cursor-pointer"]')!);
    expect(screen.getByText('找到 5 个客户')).toBeInTheDocument();
  });

  it('空步骤列表不崩溃', () => {
    const { container } = render(React.createElement(ThinkingChain, { steps: [] }));
    expect(container).toBeTruthy();
  });

  it('isComplete 为 true 时显示完成图标', () => {
    render(React.createElement(ThinkingChain, { steps: baseSteps, isComplete: true }));
    // 完成状态下不应有 spinner
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('未知 phase 降级到 planning 配置', () => {
    const unknownStep: ThinkingStep = {
      phase: 'unknown_phase' as any,
      content: '未知阶段',
      timestamp: Date.now(),
    };
    render(React.createElement(ThinkingChain, { steps: [unknownStep] }));
    // 应降级显示 planning 的标签 "规划"
    expect(screen.getByText('规划')).toBeInTheDocument();
  });
});

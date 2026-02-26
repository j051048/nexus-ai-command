import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock Sentry
vi.mock('@sentry/react', () => ({
  captureException: vi.fn(),
}));

// Inline test because ModuleErrorBoundary uses import.meta.env
// which needs to be mocked in the vitest environment
describe('ModuleErrorBoundary', () => {
  // A component that throws an error
  const ThrowingComponent = ({ shouldThrow = true }: { shouldThrow?: boolean }) => {
    if (shouldThrow) throw new Error('Test module crash');
    return <div>正常渲染</div>;
  };

  it('should render children when no error', async () => {
    const { ModuleErrorBoundary } = await import('@/components/common/ModuleErrorBoundary');
    render(
      <ModuleErrorBoundary moduleName="测试模块">
        <div>子组件内容</div>
      </ModuleErrorBoundary>
    );
    expect(screen.getByText('子组件内容')).toBeDefined();
  });

  it('should show error card with module name when child crashes', async () => {
    const { ModuleErrorBoundary } = await import('@/components/common/ModuleErrorBoundary');
    // Suppress React's error boundary console.error
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ModuleErrorBoundary moduleName="AI聊天">
        <ThrowingComponent />
      </ModuleErrorBoundary>
    );

    expect(screen.getByText('AI聊天模块加载异常')).toBeDefined();
    expect(screen.getByText('Test module crash')).toBeDefined();
    expect(screen.getByText('重试')).toBeDefined();

    consoleSpy.mockRestore();
  });

  it('should render custom fallback when provided', async () => {
    const { ModuleErrorBoundary } = await import('@/components/common/ModuleErrorBoundary');
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ModuleErrorBoundary moduleName="测试" fallback={<div>自定义错误页</div>}>
        <ThrowingComponent />
      </ModuleErrorBoundary>
    );

    expect(screen.getByText('自定义错误页')).toBeDefined();
    consoleSpy.mockRestore();
  });
});

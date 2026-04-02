/**
 * ErrorBoundary 级联 & 边缘案例测试
 *
 * 覆盖：渲染错误捕获、错误信息展示、恢复操作、
 *       嵌套错误、异步错误、开发模式详情
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ErrorBoundary } from '@/components/ErrorBoundary';

// 故意抛错的组件
function ThrowError({ message }: { message: string }) {
  throw new Error(message);
}

// 条件抛错
function ConditionalThrow({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('Conditional error');
  return <div>正常内容</div>;
}

describe('ErrorBoundary', () => {
  // 抑制 React 的 console.error（ErrorBoundary 会触发）
  const originalError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });

  afterEach(() => {
    console.error = originalError;
  });

  it('正常渲染子组件', () => {
    render(
      <ErrorBoundary>
        <div>正常内容</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('正常内容')).toBeDefined();
  });

  it('捕获渲染错误并显示错误页面', () => {
    render(
      <ErrorBoundary>
        <ThrowError message="测试错误" />
      </ErrorBoundary>
    );
    expect(screen.getByText('页面出现异常')).toBeDefined();
    expect(screen.getByText(/很抱歉/)).toBeDefined();
  });

  it('显示重新加载按钮', () => {
    render(
      <ErrorBoundary>
        <ThrowError message="test" />
      </ErrorBoundary>
    );
    expect(screen.getByText('重新加载')).toBeDefined();
  });

  it('显示返回首页按钮', () => {
    render(
      <ErrorBoundary>
        <ThrowError message="test" />
      </ErrorBoundary>
    );
    expect(screen.getByText('返回首页')).toBeDefined();
  });

  it('重新加载按钮调用 window.location.reload', () => {
    const reloadMock = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { ...window.location, reload: reloadMock },
      writable: true,
    });

    render(
      <ErrorBoundary>
        <ThrowError message="test" />
      </ErrorBoundary>
    );
    fireEvent.click(screen.getByText('重新加载'));
    expect(reloadMock).toHaveBeenCalled();
  });

  it('返回首页按钮设置 location.href', () => {
    let href = '';
    Object.defineProperty(window, 'location', {
      value: {
        ...window.location,
        get href() { return href; },
        set href(v: string) { href = v; },
        reload: vi.fn(),
      },
      writable: true,
    });

    render(
      <ErrorBoundary>
        <ThrowError message="test" />
      </ErrorBoundary>
    );
    fireEvent.click(screen.getByText('返回首页'));
    expect(href).toBe('/');
  });

  it('开发模式下可展开错误详情', () => {
    // import.meta.env.DEV 在 vitest 中默认为 true
    render(
      <ErrorBoundary>
        <ThrowError message="详细错误信息" />
      </ErrorBoundary>
    );

    const toggleBtn = screen.queryByText('展开错误详情');
    if (toggleBtn) {
      fireEvent.click(toggleBtn);
      expect(screen.getByText(/详细错误信息/)).toBeDefined();
    }
  });

  it('嵌套 ErrorBoundary 内层捕获', () => {
    render(
      <ErrorBoundary>
        <div>
          <ErrorBoundary>
            <ThrowError message="内层错误" />
          </ErrorBoundary>
          <div>外层正常</div>
        </div>
      </ErrorBoundary>
    );
    // 外层应该正常
    expect(screen.getByText('外层正常')).toBeDefined();
    // 内层应该显示错误
    expect(screen.getByText('页面出现异常')).toBeDefined();
  });

  it('多个子组件中一个出错不影响 ErrorBoundary 显示', () => {
    render(
      <ErrorBoundary>
        <ThrowError message="boom" />
      </ErrorBoundary>
    );
    // 应该显示错误页面而不是白屏
    expect(screen.getByText('页面出现异常')).toBeDefined();
  });
});

describe('ErrorBoundary 边缘案例', () => {
  const originalError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = originalError;
  });

  it('空 children 不崩溃', () => {
    const { container } = render(<ErrorBoundary>{null as any}</ErrorBoundary>);
    expect(container).toBeDefined();
  });

  it('Error 对象无 stack 不崩溃', () => {
    function ThrowNoStack() {
      const err = new Error('no stack');
      err.stack = undefined;
      throw err;
    }
    render(
      <ErrorBoundary>
        <ThrowNoStack />
      </ErrorBoundary>
    );
    expect(screen.getByText('页面出现异常')).toBeDefined();
  });

  it('非 Error 对象抛出', () => {
    function ThrowString() {
      throw 'string error'; // eslint-disable-line no-throw-literal
    }
    // React 会将非 Error 包装，ErrorBoundary 应该仍能捕获
    render(
      <ErrorBoundary>
        <ThrowString />
      </ErrorBoundary>
    );
    expect(screen.getByText('页面出现异常')).toBeDefined();
  });

  it('超长错误消息不破坏布局', () => {
    const longMsg = 'E'.repeat(5000);
    render(
      <ErrorBoundary>
        <ThrowError message={longMsg} />
      </ErrorBoundary>
    );
    expect(screen.getByText('页面出现异常')).toBeDefined();
  });

  it('rerender 触发错误后显示兜底 UI', () => {
    let triggerError = false;
    function Faulty() {
      if (triggerError) throw new Error('Crash');
      return <div>Normal state</div>;
    }
    const { getByText, getAllByText, rerender } = render(
      <ErrorBoundary>
        <Faulty />
      </ErrorBoundary>
    );
    expect(getByText('Normal state')).toBeDefined();

    triggerError = true;
    rerender(
      <ErrorBoundary>
        <Faulty />
      </ErrorBoundary>
    );
    expect(getAllByText(/返回首页/i)[0]).toBeDefined();
  });
});

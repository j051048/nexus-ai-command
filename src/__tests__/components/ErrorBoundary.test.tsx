import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { ErrorBoundary } from '../../components/ErrorBoundary';

// 为不报错压制 console.error
const originalConsoleError = console.error;

describe('ErrorBoundary (组件异常阻断测试)', () => {
  beforeEach(() => {
    console.error = vi.fn(); // 屏蔽掉 react 抛出的异常log干扰测试报告
  });

  afterEach(() => {
    console.error = originalConsoleError;
  });

  it('如果子组件正常，应当正常渲染它的子组件', () => {
    const { getByText } = render(
      <ErrorBoundary>
        <div>All is well</div>
      </ErrorBoundary>
    );
    expect(getByText('All is well')).toBeInTheDocument();
  });

  it('如果子组件发生崩溃(如 map is not a function)，边界应该接管渲染兜底UI，而不是全体白屏', () => {
    const ThrowError = () => {
      throw new Error('Test Map is not a function');
      return <div>Will not reach</div>;
    };

    const { getAllByText } = render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    // ErrorBoundary 会渲染默认的降级界面
    expect(getAllByText(/返回首页/i)[0]).toBeInTheDocument();
    expect(getAllByText(/展开错误详情/i)[0]).toBeInTheDocument();
  });
});

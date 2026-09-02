import { fireEvent, render, screen } from '@testing-library/react';
import { Activity } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';

import { OperationalMetricStrip } from '@/components/common/OperationalMetricStrip';
import { PrecisionPageHeader } from '@/components/common/PrecisionPageHeader';
import { WorkEmptyState, WorkErrorState, WorkLoadingState } from '@/components/common/WorkState';
import { Button } from '@/components/ui/button';

describe('precision work surfaces', () => {
  it('renders page hierarchy, status and actions accessibly', () => {
    render(
      <PrecisionPageHeader
        eyebrow="企业资料"
        title="AI 的企业事实库"
        description="所有生成任务都从可信资料开始。"
        icon={Activity}
        status={{ label: '检索可用', detail: '12 份资料', tone: 'success' }}
        actions={<Button>上传资料</Button>}
      />,
    );

    expect(screen.getByRole('heading', { name: 'AI 的企业事实库', level: 1 })).toBeInTheDocument();
    expect(screen.getByText('检索可用')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '上传资料' })).toBeEnabled();
  });

  it('keeps operational values in a labelled definition list', () => {
    render(
      <OperationalMetricStrip
        ariaLabel="交付质量"
        metrics={[
          { label: '证据覆盖率', value: '92%', detail: '11 条引用', tone: 'success' },
          { label: '待复核', value: 2, detail: '生成前确认', tone: 'warning' },
        ]}
      />,
    );

    const metrics = screen.getByLabelText('交付质量');
    expect(metrics).toHaveTextContent('证据覆盖率');
    expect(metrics).toHaveTextContent('92%');
    expect(metrics).toHaveTextContent('待复核');
  });

  it('exposes empty, error and loading actions without hiding state meaning', () => {
    const primary = vi.fn();
    const secondary = vi.fn();
    const retry = vi.fn();
    const { rerender } = render(
      <WorkEmptyState
        title="还没有资料"
        actionLabel="上传资料"
        onAction={primary}
        secondaryActionLabel="查看示例"
        onSecondaryAction={secondary}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '上传资料' }));
    fireEvent.click(screen.getByRole('button', { name: '查看示例' }));
    expect(primary).toHaveBeenCalledOnce();
    expect(secondary).toHaveBeenCalledOnce();

    rerender(<WorkErrorState title="资料加载失败" onAction={retry} />);
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(retry).toHaveBeenCalledOnce();

    rerender(<WorkLoadingState title="正在建立索引" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true');
  });
});

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { CompactStageRail } from '@/components/workflow/CompactStageRail';

const stages = [
  { id: 'brief', label: '客户简报', shortLabel: '需求', description: '客户、场景与预算' },
  { id: 'draft', label: '方案成稿', shortLabel: '成稿', description: '章节与证据引用' },
] as const;

describe('CompactStageRail', () => {
  it('shows only the active stage description and keeps every stage operable', () => {
    const onStageChange = vi.fn();
    render(
      <CompactStageRail
        label="方案作业阶段"
        stages={[...stages]}
        activeStage="brief"
        completedStages={[]}
        onStageChange={onStageChange}
      />,
    );

    expect(screen.getByText('客户、场景与预算')).toBeInTheDocument();
    expect(screen.queryByText('章节与证据引用')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /成稿/ }));
    expect(onStageChange).toHaveBeenCalledWith('draft');
  });
});

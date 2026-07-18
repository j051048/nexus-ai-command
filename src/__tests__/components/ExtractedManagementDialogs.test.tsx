import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ModelEditorDialog } from '@/components/ai/model-management/ModelEditorDialog';
import { EMPTY_MODEL } from '@/components/ai/model-management/modelManagementConfig';
import { QuickAddModelDialog } from '@/components/ai/model-management/QuickAddModelDialog';
import { VMDCreateTaskDialog } from '@/components/vmd/VMDCreateTaskDialog';

describe('拆分后的管理对话框契约', () => {
  it('保留模型编辑的保存与测试入口', () => {
    const onSave = vi.fn();
    const onTest = vi.fn();

    render(
      <ModelEditorDialog
        open
        onOpenChange={vi.fn()}
        isEditing
        model={{ ...EMPTY_MODEL, id: 'model-1', name: 'DeepSeek V4 Flash' }}
        setModel={vi.fn()}
        onSave={onSave}
        onTest={onTest}
        testingId={null}
        testResult={null}
        isSaving={false}
      />
    );

    expect(screen.getByText('编辑模型')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '测试连通性' }));
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    expect(onTest).toHaveBeenCalledWith('model-1');
    expect(onSave).toHaveBeenCalledOnce();
  });

  it('保留模型市场的一键添加确认', () => {
    const onConfirm = vi.fn();

    render(
      <QuickAddModelDialog
        model={{
          model_id: 'deepseek-v4-flash',
          name: 'DeepSeek V4 Flash',
          provider: 'openai-compatible',
          provider_label: 'OpenAI 兼容',
          type: 'chat',
          context_window: 128000,
          max_tokens: 8192,
          supports_tools: true,
          supports_streaming: true,
          input_price_per_1m: 0.1,
          output_price_per_1m: 0.2,
          tags: ['default'],
          already_added: false,
          has_metadata: true,
          available_from: ['gateway'],
        }}
        onOpenChange={vi.fn()}
        onConfirm={onConfirm}
        isPending={false}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '确认添加' }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it('保留 VMD 新任务创建入口及领域字段', () => {
    const onCreate = vi.fn();

    render(
      <VMDCreateTaskDialog
        open
        onOpenChange={vi.fn()}
        title="新品上市"
        setTitle={vi.fn()}
        description=""
        setDescription={vi.fn()}
        scene="product_launch"
        setScene={vi.fn()}
        priority="medium"
        setPriority={vi.fn()}
        deadline=""
        setDeadline={vi.fn()}
        instrumentLine="spectroscopy"
        setInstrumentLine={vi.fn()}
        applicationField=""
        setApplicationField={vi.fn()}
        productModels=""
        setProductModels={vi.fn()}
        onCreate={onCreate}
        isPending={false}
      />
    );

    expect(screen.getByLabelText('任务标题')).toHaveValue('新品上市');
    expect(screen.getByText('行业上下文')).toBeInTheDocument();
    expect(screen.getByText('产品线')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '创建任务' }));
    expect(onCreate).toHaveBeenCalledOnce();
  });
});

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AIExecutionPolicyPanel } from '@/components/settings/AIExecutionPolicyPanel';

const savePolicy = vi.fn();

const preset = (mode: 'economy' | 'balanced' | 'strict', calls: number) => ({
  version: 'test-v1',
  mode,
  primary_model: 'deepseek-v4-flash',
  embedding_model: 'text-embedding-3-small',
  rerank_model: 'bge-reranker-v2-m3',
  premium_model: null,
  premium_manual_only: true,
  allow_llm_router: false,
  scheduled_primary_only: true,
  max_calls: calls,
  max_verifications: mode === 'economy' ? 0 : 1,
  max_iterations: calls,
  max_input_tokens: 24_000,
  max_output_tokens: 4_096,
  max_task_cost_usd: mode === 'economy' ? 0.03 : mode === 'strict' ? 0.18 : 0.08,
  max_latency_ms: mode === 'economy' ? 35_000 : mode === 'strict' ? 120_000 : 60_000,
  context_tool_limit: 12,
  retain_inference_receipts: true,
});

vi.mock('@/hooks/useAIExecutionPolicy', () => ({
  useAIExecutionPolicy: () => ({
    data: {
      policy: preset('balanced', 2),
      presets: {
        economy: preset('economy', 1),
        balanced: preset('balanced', 2),
        strict: preset('strict', 3),
      },
    },
    isLoading: false,
  }),
  useUpdateAIExecutionPolicy: () => ({
    mutateAsync: savePolicy,
    isPending: false,
  }),
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

describe('AIExecutionPolicyPanel', () => {
  beforeEach(() => savePolicy.mockReset().mockResolvedValue({}));

  it('shows a simple three-mode policy instead of model selection', () => {
    render(<AIExecutionPolicyPanel />);

    expect(screen.getByText('省成本')).toBeInTheDocument();
    expect(screen.getByText('智能平衡')).toBeInTheDocument();
    expect(screen.getByText('严谨优先')).toBeInTheDocument();
    expect(screen.getByText(/deepseek-v4-flash/)).toBeInTheDocument();
    expect(screen.queryByText('gemini-3.1-pro-preview')).not.toBeInTheDocument();
  });

  it('saves only the selected execution mode', async () => {
    render(<AIExecutionPolicyPanel />);

    fireEvent.click(screen.getByRole('button', { name: /严谨优先/ }));
    fireEvent.click(screen.getByRole('button', { name: '保存执行方式' }));

    await waitFor(() => {
      expect(savePolicy).toHaveBeenCalledWith({ mode: 'strict' });
    });
  });
});

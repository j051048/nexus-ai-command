import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/features/deliverables/artifactApi', () => ({
  getArtifactPreview: vi.fn(), downloadArtifact: vi.fn(), reviseArtifact: vi.fn(),
}));

import { ArtifactPreviewButton } from '@/components/deliverables/ArtifactPreviewButton';
import { parseDeliveryCriteria } from '@/components/deliverables/DeliveryRequirementsEditor';
import { downloadArtifact, getArtifactPreview, reviseArtifact, type ArtifactPreview } from '@/features/deliverables/artifactApi';

const fixture = {
  id: 'artifact-1', title: '光谱客户方案', content_markdown: '# 正式方案\n\n| 配置 | 依据 |\n| --- | --- |\n| 光谱仪 | 企业资料 |\n\n![remote](https://example.invalid/tracker.png)',
  approval_status: 'pending', quality: { ready: false, findings: [{ code: 'missing', message: '补充售后条款' }], metrics: { character_count: 1200 } },
  requirements: { minimum_character_count: 3000 }, sources: [{ title: '产品手册', document_id: 'doc-1' }], usage: {},
  checkpoint_hits: 2, requested_formats: ['docx', 'pdf', 'xlsx'],
} as ArtifactPreview;

beforeEach(() => { vi.mocked(getArtifactPreview).mockResolvedValue(fixture); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe('result-first artifact preview', () => {
  it('loads only when opened, renders safe content and downloads the selected format as draft', async () => {
    render(<ArtifactPreviewButton artifactId="artifact-1" />);
    expect(getArtifactPreview).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '预览与修订' }));
    expect(await screen.findByRole('heading', { name: '正式方案' })).toBeInTheDocument();
    expect(document.querySelector('img')).toBeNull();
    fireEvent.change(screen.getByRole('combobox', { name: '文件格式' }), { target: { value: 'pdf' } });
    fireEvent.click(screen.getByRole('button', { name: '下载审核草稿' }));
    await waitFor(() => expect(downloadArtifact).toHaveBeenCalledWith('artifact-1', 'pdf', '审核草稿-光谱客户方案'));
  });

  it('preserves idempotency when a revision request must be retried', async () => {
    vi.mocked(reviseArtifact).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ id: 'job-new' } as never);
    render(<ArtifactPreviewButton artifactId="artifact-1" />);
    fireEvent.click(screen.getByRole('button', { name: '预览与修订' }));
    await screen.findByRole('heading', { name: '正式方案' });
    fireEvent.click(screen.getByText('修改要求'));
    fireEvent.change(screen.getByLabelText('修订要求'), { target: { value: '完善安装与售后条款' } });
    fireEvent.click(screen.getByRole('button', { name: '生成修订稿' }));
    await waitFor(() => expect(screen.getByRole('button', { name: '生成修订稿' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: '生成修订稿' }));
    await waitFor(() => expect(reviseArtifact).toHaveBeenCalledTimes(2));
    expect(vi.mocked(reviseArtifact).mock.calls[0][2]).toBe(vi.mocked(reviseArtifact).mock.calls[1][2]);
  });

  it('clears stale content when another artifact is selected and fails closed', async () => {
    const view = render(<ArtifactPreviewButton artifactId="artifact-1" />);
    fireEvent.click(screen.getByRole('button', { name: '预览与修订' }));
    await screen.findByRole('heading', { name: '正式方案' });
    vi.mocked(getArtifactPreview).mockRejectedValue(new Error('forbidden'));
    view.rerender(<ArtifactPreviewButton artifactId="artifact-2" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('引用资料已变更');
    expect(screen.queryByRole('heading', { name: '正式方案' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '下载审核草稿' })).not.toBeInTheDocument();
  });

  it('deduplicates and bounds explicit acceptance requirements', () => {
    expect(parseDeliveryCriteria('安装培训\n安装培训\n售后服务', '永久保证').value.required_facts).toHaveLength(2);
    expect(parseDeliveryCriteria('短', '').valid).toBe(false);
    expect(parseDeliveryCriteria(Array.from({ length: 25 }, (_, i) => `条件${i}`).join('\n'), '').valid).toBe(false);
  });
});

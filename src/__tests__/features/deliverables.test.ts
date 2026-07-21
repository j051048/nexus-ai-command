import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  addDeliverable,
  announceDeliverable,
  DELIVERABLE_READY_EVENT,
  readDeliverables,
  removeDeliverable,
} from '@/features/deliverables/deliverableStore';
import { markdownTableRows, titleFromContent } from '@/features/deliverables/exportContent';
import type { DeliverableRecord } from '@/features/deliverables/types';

describe('deliverable delivery layer', () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    vi.mocked(window.localStorage.getItem).mockImplementation((key) => storage.get(key) ?? null);
    vi.mocked(window.localStorage.setItem).mockImplementation((key, value) => { storage.set(key, value); });
    vi.mocked(window.localStorage.removeItem).mockImplementation((key) => { storage.delete(key); });
  });

  it('stores metadata by tenant without persisting generated file contents', () => {
    const record: DeliverableRecord = {
      id: 'result-1',
      title: '液相色谱方案',
      filename: '液相色谱方案.docx',
      format: 'docx',
      source: 'solution',
      sourceLabel: '方案作战',
      sourcePath: '/growth/solutions?project=1',
      createdAt: '2026-07-21T08:00:00.000Z',
    };

    addDeliverable('org-a', record);

    expect(readDeliverables('org-a')).toEqual([record]);
    expect(readDeliverables('org-b')).toEqual([]);
    expect(removeDeliverable('org-a', record.id)).toEqual([]);
  });

  it('announces completed artifacts to the global tray', () => {
    const listener = vi.fn();
    window.addEventListener(DELIVERABLE_READY_EVENT, listener);

    const record = announceDeliverable({
      title: '投标审阅报告',
      filename: '投标审阅报告.pdf',
      format: 'pdf',
      source: 'tender',
      sourceLabel: '投标作战',
      sourcePath: '/tender-analysis',
    });

    expect(record.id).toMatch(/^deliverable-/);
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(DELIVERABLE_READY_EVENT, listener);
  });

  it('turns markdown tables into spreadsheet rows', () => {
    const rows = markdownTableRows([
      '| 型号 | 检出限 |',
      '| --- | ---: |',
      '| LC-100 | 0.1 ppb |',
      '| LC-200 | 0.05 ppb |',
    ].join('\n'));

    expect(rows).toEqual([
      { 型号: 'LC-100', 检出限: '0.1 ppb' },
      { 型号: 'LC-200', 检出限: '0.05 ppb' },
    ]);
  });

  it('creates a stable file title from the first markdown heading', () => {
    expect(titleFromContent('# 制药企业液相色谱解决方案\n正文')).toBe('制药企业液相色谱解决方案');
  });
});


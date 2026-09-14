import { describe, expect, it } from 'vitest';
import { unwrapApiData, unwrapApiList } from '@/api/response';

describe('API response envelopes', () => {
  it('supports current envelopes and legacy raw responses', () => {
    const tools = { tools: [{ name: 'search' }], count: 1 };
    expect(unwrapApiData({ success: true, data: tools })).toEqual(tools);
    expect(unwrapApiData(tools)).toEqual(tools);
    expect(unwrapApiList({ success: true, data: [] })).toEqual([]);
    expect(unwrapApiList([{ id: 'product' }])).toEqual([{ id: 'product' }]);
  });

  it('does not disguise an API failure as an empty result', () => {
    expect(() => unwrapApiList({ success: false, data: [] })).toThrow();
    expect(() => unwrapApiList(JSON.parse('{"data":null}'))).toThrow();
    expect(() => unwrapApiList(JSON.parse('{"data":{"items":[]}}'))).toThrow();
  });
});

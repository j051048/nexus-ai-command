import { describe, expect, it } from 'vitest';

describe('test network isolation', () => {
  it('rejects an unmocked external request', async () => {
    await expect(fetch('https://unexpected-test-network.invalid')).rejects.toThrow(
      'Unexpected network request in frontend test'
    );
  });
});

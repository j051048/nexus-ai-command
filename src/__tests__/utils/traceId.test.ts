import { describe, it, expect } from 'vitest';
import { getTraceId, resetTraceSession } from '@/api/aiClient';

describe('aiClient TraceID', () => {
  it('should generate trace IDs with fe- prefix', () => {
    const traceId = getTraceId();
    expect(traceId).toMatch(/^fe-/);
  });

  it('should generate unique trace IDs per call', () => {
    const id1 = getTraceId();
    const id2 = getTraceId();
    expect(id1).not.toBe(id2);
  });

  it('should share session prefix across calls', () => {
    const id1 = getTraceId();
    const id2 = getTraceId();
    // Both should share the same session prefix (first two segments)
    const prefix1 = id1.split('-').slice(0, 2).join('-');
    const prefix2 = id2.split('-').slice(0, 2).join('-');
    expect(prefix1).toBe(prefix2);
  });

  it('should generate new session prefix after reset', () => {
    const id1 = getTraceId();
    resetTraceSession();
    const id2 = getTraceId();
    const prefix1 = id1.split('-').slice(0, 2).join('-');
    const prefix2 = id2.split('-').slice(0, 2).join('-');
    expect(prefix1).not.toBe(prefix2);
  });
});

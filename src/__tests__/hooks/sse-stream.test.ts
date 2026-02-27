/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ─── SSE 流解析工具函数 ──────────────────────────────────────

/**
 * 模拟解析 SSE 事件流，与 useAIStream 中 parseBackendStream 逻辑一致
 */
function parseSSELines(rawText: string): Array<{
  type: 'content' | 'status' | 'thinking_step' | 'thinking_complete' | 'confirmation' | 'sanitized' | 'done';
  data?: any;
}> {
  const events: Array<{ type: string; data?: any }> = [];
  const lines = rawText.split('\n');

  for (const rawLine of lines) {
    let line = rawLine.trim();
    if (line.endsWith('\r')) line = line.slice(0, -1);

    // Skip comments and empty lines
    if (line.startsWith(':') || line === '') continue;
    if (!line.startsWith('data: ')) continue;

    const jsonStr = line.slice(6).trim();
    if (jsonStr === '[DONE]') {
      events.push({ type: 'done' });
      continue;
    }

    try {
      const parsed = JSON.parse(jsonStr);

      if (parsed.thinking_step) {
        events.push({ type: 'thinking_step', data: parsed.thinking_step });
        continue;
      }

      if (parsed.thinking_chain_complete) {
        events.push({ type: 'thinking_complete', data: { total_steps: parsed.total_steps } });
        continue;
      }

      if (parsed.status) {
        events.push({ type: 'status', data: parsed.status });
        continue;
      }

      if (parsed.confirmation_required) {
        events.push({ type: 'confirmation', data: parsed.confirmation_required });
        continue;
      }

      if (parsed.sanitized_content) {
        events.push({ type: 'sanitized', data: parsed.sanitized_content });
        continue;
      }

      const content = parsed.choices?.[0]?.delta?.content;
      if (content) {
        events.push({ type: 'content', data: content });
      }
    } catch {
      // Incomplete JSON, skip
    }
  }

  return events as any;
}

// ─── Tests ──────────────────────────────────────────────────

describe('SSE 流解析测试', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('解析普通内容增量', () => {
    const raw = [
      'data: {"choices":[{"delta":{"content":"你"}}]}',
      'data: {"choices":[{"delta":{"content":"好"}}]}',
      'data: [DONE]',
    ].join('\n');

    const events = parseSSELines(raw);

    expect(events).toHaveLength(3);
    expect(events[0]).toEqual({ type: 'content', data: '你' });
    expect(events[1]).toEqual({ type: 'content', data: '好' });
    expect(events[2]).toEqual({ type: 'done' });
  });

  it('解析 thinking_step 事件', () => {
    const raw = [
      'data: {"thinking_step":{"phase":"planning","content":"分析用户意图","timestamp":1700000000}}',
      'data: {"thinking_step":{"phase":"executing","content":"调用销售工具","tool_name":"get_sales","timestamp":1700000001}}',
      'data: {"thinking_chain_complete":true,"total_steps":2}',
      'data: {"choices":[{"delta":{"content":"根据数据分析..."}}]}',
      'data: [DONE]',
    ].join('\n');

    const events = parseSSELines(raw);

    expect(events).toHaveLength(5);
    expect(events[0].type).toBe('thinking_step');
    expect(events[0].data.phase).toBe('planning');
    expect(events[1].type).toBe('thinking_step');
    expect(events[1].data.tool_name).toBe('get_sales');
    expect(events[2].type).toBe('thinking_complete');
    expect(events[2].data.total_steps).toBe(2);
    expect(events[3].type).toBe('content');
    expect(events[4].type).toBe('done');
  });

  it('解析 status 事件', () => {
    const raw = [
      'data: {"status":"正在连接后端服务..."}',
      'data: {"choices":[{"delta":{"content":"结果"}}]}',
      'data: [DONE]',
    ].join('\n');

    const events = parseSSELines(raw);

    expect(events[0]).toEqual({ type: 'status', data: '正在连接后端服务...' });
    expect(events[1]).toEqual({ type: 'content', data: '结果' });
  });

  it('解析 confirmation_required 事件 (HITL)', () => {
    const raw =
      'data: {"confirmation_required":{"tool_name":"delete_record","message":"确认删除？","args":{"id":"123"}}}';

    const events = parseSSELines(raw);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('confirmation');
    expect(events[0].data.tool_name).toBe('delete_record');
    expect(events[0].data.args.id).toBe('123');
  });

  it('解析 sanitized_content 事件', () => {
    const raw = 'data: {"sanitized_content":"已修正内容"}';

    const events = parseSSELines(raw);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: 'sanitized', data: '已修正内容' });
  });

  it('忽略注释行和空行', () => {
    const raw = [
      ': this is a comment',
      '',
      'data: {"choices":[{"delta":{"content":"hi"}}]}',
      '',
      ': another comment',
      'data: [DONE]',
    ].join('\n');

    const events = parseSSELines(raw);

    expect(events).toHaveLength(2);
    expect(events[0].type).toBe('content');
    expect(events[1].type).toBe('done');
  });

  it('跳过非 data: 开头的行', () => {
    const raw = [
      'event: message',
      'id: 1',
      'data: {"choices":[{"delta":{"content":"内容"}}]}',
      'data: [DONE]',
    ].join('\n');

    const events = parseSSELines(raw);

    expect(events).toHaveLength(2);
    expect(events[0].data).toBe('内容');
  });

  it('处理无 content 的 delta 事件', () => {
    const raw = [
      'data: {"choices":[{"delta":{}}]}',
      'data: {"choices":[{"delta":{"content":"有内容"}}]}',
      'data: [DONE]',
    ].join('\n');

    const events = parseSSELines(raw);

    // 第一条无 content，应被跳过
    expect(events).toHaveLength(2);
    expect(events[0].data).toBe('有内容');
  });

  it('累积内容增量还原完整消息', () => {
    const raw = [
      'data: {"choices":[{"delta":{"content":"Hello"}}]}',
      'data: {"choices":[{"delta":{"content":" "}}]}',
      'data: {"choices":[{"delta":{"content":"World"}}]}',
      'data: [DONE]',
    ].join('\n');

    const events = parseSSELines(raw);
    const contentEvents = events.filter(e => e.type === 'content');
    const fullContent = contentEvents.map(e => e.data).join('');

    expect(fullContent).toBe('Hello World');
  });
});

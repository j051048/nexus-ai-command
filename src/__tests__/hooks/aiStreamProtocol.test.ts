import { describe, expect, it, vi } from 'vitest';

import {
  MAX_ASSISTANT_CONTENT_CHARS,
  STREAM_TRUNCATION_NOTICE,
  appendStreamContent,
  parseAIResponseStream,
} from '@/hooks/ai-stream/protocol';

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    }),
    { headers: { 'content-type': 'text/event-stream' } }
  );
}

describe('AI stream protocol', () => {
  it('dispatches state events and accumulates content across chunks', async () => {
    const onUpdate = vi.fn();
    const onStatus = vi.fn();
    const onConfirmationRequired = vi.fn();
    const onActivity = vi.fn();

    await parseAIResponseStream(
      streamResponse([
        'data: {"status":"planning"}\n',
        'data: {"confirmation_required":{"tool_name":"send_email","message":"confirm","args":{}}}\n',
        'data: {"choices":[{"delta":{"content":"hello "}}]}\n',
        'data: {"choices":[{"delta":{"content":"world"}}]}\n',
        'data: [DONE]\n',
      ]),
      { onUpdate, onStatus, onConfirmationRequired, onActivity }
    );

    expect(onStatus).toHaveBeenCalledWith('planning');
    expect(onStatus).toHaveBeenCalledWith(undefined);
    expect(onConfirmationRequired).toHaveBeenCalledWith(
      expect.objectContaining({ tool_name: 'send_email' })
    );
    expect(onUpdate).toHaveBeenLastCalledWith('hello world', expect.any(String));
    expect(onActivity).toHaveBeenCalledTimes(2);
  });

  it('parses a final SSE event even when the stream has no trailing newline', async () => {
    const onUpdate = vi.fn();

    await parseAIResponseStream(
      streamResponse(['data: {"choices":[{"delta":{"content":"final"}}]}']),
      { onUpdate }
    );

    expect(onUpdate).toHaveBeenCalledWith('final', expect.any(String));
  });

  it('supports non-SSE JSON and raw text responses', async () => {
    const jsonUpdate = vi.fn();
    const textUpdate = vi.fn();

    await parseAIResponseStream(
      new Response('{"choices":[{"message":{"content":"json reply"}}]}', {
        headers: { 'content-type': 'application/json' },
      }),
      { onUpdate: jsonUpdate }
    );
    await parseAIResponseStream(
      new Response('plain reply', {
        headers: { 'content-type': 'application/octet-stream' },
      }),
      { onUpdate: textUpdate }
    );

    expect(jsonUpdate).toHaveBeenCalledWith('json reply', expect.any(String));
    expect(textUpdate).toHaveBeenCalledWith('plain reply', expect.any(String));
  });

  it('bounds assistant content without appending duplicate notices', () => {
    const oversized = 'x'.repeat(MAX_ASSISTANT_CONTENT_CHARS + 20);
    const truncated = appendStreamContent('', oversized);

    expect(truncated).toHaveLength(MAX_ASSISTANT_CONTENT_CHARS + STREAM_TRUNCATION_NOTICE.length);
    expect(appendStreamContent(truncated, 'ignored')).toBe(truncated);
  });
});

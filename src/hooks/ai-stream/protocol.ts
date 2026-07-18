import type { ThinkingStep } from '@/types/nexus';

export const MAX_ASSISTANT_CONTENT_CHARS = 30_000;
export const MAX_THINKING_STEPS = 80;
export const MAX_SSE_BUFFER_CHARS = 64_000;
export const STREAM_TRUNCATION_NOTICE =
  '\n\n[Stream truncated: response exceeded the client safety limit.]';

export interface ConfirmationRequest {
  tool_name: string;
  message: string;
  args: Record<string, unknown>;
  modifiable?: boolean;
  confirmation_type?: 'irreversible' | 'high_value' | 'bulk' | 'external' | 'escalation' | '';
}

export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'email' | 'select' | 'date' | 'textarea' | 'checkbox';
  required?: boolean;
  default_value?: string;
  options?: string[];
  placeholder?: string;
  step?: number;
}

export interface AskUserRequest {
  question: string;
  options: string[];
  context: string;
  fields?: FormField[];
}

export interface CircuitBreakInfo {
  reason: string;
  suggestion: string;
}

export interface QuotaInfo {
  tokens_used: number;
  tokens_limit: number;
  tokens_remaining: number;
  requests: number;
  requests_limit: number;
  cost_usd: number;
}

export interface StreamCallbacks {
  onUpdate?: (content: string, id: string) => void;
  onThinkingStep?: (step: ThinkingStep) => void;
  onThinkingComplete?: (totalSteps: number) => void;
  onToolProgress?: (progress: { tool_name: string; status: string; duration_ms?: number }) => void;
  onOrchestration?: (event: Record<string, unknown>) => void;
}

export interface StreamEventHandlers extends StreamCallbacks {
  onActivity?: () => void;
  onStatus?: (status: string | undefined) => void;
  onConfirmationRequired?: (request: ConfirmationRequest) => void;
  onAskUser?: (request: AskUserRequest) => void;
  onCircuitBreak?: (info: CircuitBreakInfo) => void;
  onQuota?: (quota: QuotaInfo) => void;
  onFollowUpSuggestions?: (suggestions: string[]) => void;
}

export function appendStreamContent(current: string, delta: string): string {
  if (!delta) return current;
  const next = current + delta;
  if (next.length <= MAX_ASSISTANT_CONTENT_CHARS) return next;
  if (current.endsWith(STREAM_TRUNCATION_NOTICE)) return current;
  return next.slice(0, MAX_ASSISTANT_CONTENT_CHARS) + STREAM_TRUNCATION_NOTICE;
}

function responseContent(payload: Record<string, unknown>): string {
  const choices = payload.choices as
    | Array<{
        message?: { content?: string };
        delta?: { content?: string };
      }>
    | undefined;
  const error = payload.error as { message?: string } | string | undefined;
  return (
    choices?.[0]?.message?.content ||
    choices?.[0]?.delta?.content ||
    (typeof error === 'string' ? error : error?.message) ||
    JSON.stringify(payload)
  );
}

/** Parse the backend's OpenAI-compatible SSE protocol without owning React state. */
export async function parseAIResponseStream(
  response: Response,
  handlers: StreamEventHandlers = {}
): Promise<void> {
  if (!response.body) throw new Error('响应体为空');

  const assistantMsgId = Date.now().toString();
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('text/event-stream') && !contentType.includes('text/plain')) {
    const text = await response.text();
    try {
      const json = JSON.parse(text) as Record<string, unknown>;
      handlers.onUpdate?.(responseContent(json), assistantMsgId);
    } catch {
      if (text) handlers.onUpdate?.(text, assistantMsgId);
    }
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let textBuffer = '';
  let assistantContent = '';
  let streamDone = false;
  let framePending = false;
  let frameId: number | ReturnType<typeof setTimeout> = 0;
  let lastFlushedContent = '';
  const requestFrame =
    globalThis.requestAnimationFrame ??
    ((callback: FrameRequestCallback) => setTimeout(callback, 0));
  const cancelFrame =
    globalThis.cancelAnimationFrame ??
    ((id: number | ReturnType<typeof setTimeout>) => clearTimeout(id));

  const flushContent = () => {
    framePending = false;
    if (assistantContent !== lastFlushedContent) {
      lastFlushedContent = assistantContent;
      handlers.onUpdate?.(assistantContent, assistantMsgId);
    }
  };
  const scheduleFlush = () => {
    if (!framePending) {
      framePending = true;
      frameId = requestFrame(flushContent);
    }
  };

  while (true) {
    let readResult: ReadableStreamReadResult<Uint8Array>;
    try {
      readResult = await reader.read();
    } catch (error) {
      if (assistantContent) {
        if (framePending) {
          cancelFrame(frameId);
          flushContent();
        }
        assistantContent += '\n\n⚠️ 网络中断，回复可能不完整。请检查网络后重试。';
        handlers.onUpdate?.(assistantContent, assistantMsgId);
      }
      throw error;
    }

    const { done, value } = readResult;
    if (done) break;
    textBuffer += decoder.decode(value, { stream: true });
    if (textBuffer.length > MAX_SSE_BUFFER_CHARS) {
      textBuffer = textBuffer.slice(-MAX_SSE_BUFFER_CHARS);
    }

    let newlineIndex: number;
    while ((newlineIndex = textBuffer.indexOf('\n')) !== -1) {
      let line = textBuffer.slice(0, newlineIndex);
      textBuffer = textBuffer.slice(newlineIndex + 1);
      if (line.endsWith('\r')) line = line.slice(0, -1);
      if (line.startsWith(':') || line.trim() === '') continue;
      if (!line.startsWith('data: ')) continue;

      const jsonText = line.slice(6).trim();
      if (jsonText === '[DONE]') {
        streamDone = true;
        break;
      }

      try {
        const parsed = JSON.parse(jsonText) as Record<string, unknown>;
        const choices = parsed.choices as Array<{ delta?: { content?: string } }> | undefined;
        const content = choices?.[0]?.delta?.content;

        if (parsed.thinking_step) {
          handlers.onThinkingStep?.(parsed.thinking_step as ThinkingStep);
          continue;
        }
        if (parsed.thinking_chain_complete) {
          handlers.onThinkingComplete?.(Number(parsed.total_steps) || 0);
          continue;
        }
        if (parsed.status) {
          handlers.onStatus?.(String(parsed.status));
          continue;
        }
        if (parsed.confirmation_required) {
          handlers.onConfirmationRequired?.(parsed.confirmation_required as ConfirmationRequest);
          continue;
        }
        if (parsed.ask_user) {
          handlers.onAskUser?.(parsed.ask_user as AskUserRequest);
          continue;
        }
        if (parsed.circuit_break) {
          handlers.onCircuitBreak?.(parsed.circuit_break as CircuitBreakInfo);
          continue;
        }
        if (parsed.tool_progress) {
          handlers.onToolProgress?.(
            parsed.tool_progress as {
              tool_name: string;
              status: string;
              duration_ms?: number;
            }
          );
          handlers.onActivity?.();
          continue;
        }
        if (parsed.sanitized_content) {
          assistantContent = appendStreamContent('', String(parsed.sanitized_content));
          scheduleFlush();
          continue;
        }
        if (parsed.quota) {
          handlers.onQuota?.(parsed.quota as QuotaInfo);
          continue;
        }
        if (parsed.follow_up_suggestions) {
          handlers.onFollowUpSuggestions?.(parsed.follow_up_suggestions as string[]);
          continue;
        }
        if (parsed.orchestration) {
          handlers.onOrchestration?.(parsed.orchestration as Record<string, unknown>);
          continue;
        }
        if (content) {
          handlers.onStatus?.(undefined);
          assistantContent = appendStreamContent(assistantContent, content);
          scheduleFlush();
          handlers.onActivity?.();
          if (assistantContent.endsWith(STREAM_TRUNCATION_NOTICE)) {
            await reader.cancel().catch(() => undefined);
            streamDone = true;
            break;
          }
        }
      } catch {
        textBuffer = line + '\n' + textBuffer;
        break;
      }
    }
    if (streamDone) break;
  }

  if (framePending) {
    cancelFrame(frameId);
    flushContent();
  } else if (assistantContent !== lastFlushedContent) {
    flushContent();
  }

  if (!assistantContent && textBuffer.trim()) {
    const leftover = textBuffer.trim();
    const jsonText = leftover.startsWith('data: ') ? leftover.slice(6).trim() : leftover;
    try {
      const payload = JSON.parse(jsonText) as Record<string, unknown>;
      const content = responseContent(payload);
      if (content) handlers.onUpdate?.(content, assistantMsgId);
    } catch {
      if (leftover && !leftover.startsWith('data: ')) {
        handlers.onUpdate?.(leftover, assistantMsgId);
      }
    }
  }
}

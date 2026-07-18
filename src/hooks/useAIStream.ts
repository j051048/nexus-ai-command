import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { attemptEnhancedDirectStream } from '@/hooks/ai-stream/enhancedDirect';
import {
  MAX_THINKING_STEPS,
  parseAIResponseStream,
  type AskUserRequest,
  type CircuitBreakInfo,
  type ConfirmationRequest,
  type FormField,
  type QuotaInfo,
  type StreamCallbacks,
} from '@/hooks/ai-stream/protocol';
import { useNetworkStatus } from '@/hooks/ai-stream/useNetworkStatus';
import { supabase } from '@/integrations/supabase/client';
import { getApiBaseUrl } from '@/lib/apiConfig';
import type { AIMessage, ThinkingStep } from '@/types/nexus';

const ENABLE_BROWSER_AI_PROXY_FALLBACK =
  import.meta.env.VITE_ENABLE_BROWSER_AI_PROXY_FALLBACK === 'true';

interface UseAIStreamProps {
  userId: string;
  onMessageUpdate?: (messages: AIMessage[]) => void;
}

export type {
  AskUserRequest,
  CircuitBreakInfo,
  ConfirmationRequest,
  FormField,
  QuotaInfo,
} from '@/hooks/ai-stream/protocol';

export function useAIStream({ userId }: UseAIStreamProps) {
  const [isTyping, setIsTyping] = useState(false);
  const [aiStatus, setAiStatus] = useState<string | undefined>();
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  const [isThinkingComplete, setIsThinkingComplete] = useState(false);
  const [pendingConfirmation, setPendingConfirmation] = useState<ConfirmationRequest | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<AskUserRequest | null>(null);
  const [circuitBreak, setCircuitBreak] = useState<CircuitBreakInfo | null>(null);
  const [quotaInfo, setQuotaInfo] = useState<QuotaInfo | null>(null);
  const [followUpSuggestions, setFollowUpSuggestions] = useState<string[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [sessionId, setSessionId] = useState<string>(
    `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  );
  const sessionIdRef = useRef<string>(sessionId);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);
  const lastRequestRef = useRef<{
    messages: Array<{ role: string; content: string }>;
    agent?: string;
  } | null>(null);
  const pendingConfirmationRef = useRef<ConfirmationRequest | null>(null);
  pendingConfirmationRef.current = pendingConfirmation;

  const isOffline = useNetworkStatus();

  /** Tier 1 primary: Zeabur backend directly */
  const getBackendUrl = useCallback(() => {
    let url = getApiBaseUrl();
    if (!url.startsWith('http')) {
      url = `https://${url}`;
    }
    if (url.endsWith('/')) {
      url = url.slice(0, -1);
    }
    return `${url}/api/chat`;
  }, []);

  /** Tier 1 fallback: Supabase Edge Function proxy → Zeabur backend */
  const getEdgeFunctionUrl = useCallback(() => {
    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
    return `${supabaseUrl}/functions/v1/ai-chat`;
  }, []);

  /**
   * Parse an SSE stream from the backend (or proxy).
   * Handles thinking steps, status events, sanitized content, and content deltas.
   * Also handles non-SSE JSON responses gracefully.
   */
  const parseBackendStream = (
    response: Response,
    onUpdate?: (content: string, id: string) => void,
    onThinkingStep?: (step: ThinkingStep) => void,
    onThinkingComplete?: (totalSteps: number) => void,
    onToolProgress?: (progress: {
      tool_name: string;
      status: string;
      duration_ms?: number;
    }) => void,
    onOrchestration?: (event: Record<string, unknown>) => void,
    onActivity?: () => void
  ) =>
    parseAIResponseStream(response, {
      onUpdate,
      onThinkingStep: (step) => {
        setThinkingSteps((prev) => [...prev.slice(-(MAX_THINKING_STEPS - 1)), step]);
        onThinkingStep?.(step);
      },
      onThinkingComplete: (totalSteps) => {
        setIsThinkingComplete(true);
        onThinkingComplete?.(totalSteps);
      },
      onToolProgress,
      onOrchestration,
      onActivity,
      onStatus: setAiStatus,
      onConfirmationRequired: setPendingConfirmation,
      onAskUser: setPendingQuestion,
      onCircuitBreak: setCircuitBreak,
      onQuota: setQuotaInfo,
      onFollowUpSuggestions: setFollowUpSuggestions,
    });

  const streamChat = useCallback(
    async (
      input: string,
      history: AIMessage[],
      agent?: string,
      callbacks?: StreamCallbacks | ((content: string, id: string) => void),
      options?: {
        system_confirmed?: boolean;
        confirmed_tool?: { tool_name: string; args: Record<string, unknown> };
        vmd_agent_code?: string;
        scene_code?: string;
        imageUrls?: string[];
      }
    ) => {
      setIsTyping(true);
      setAiStatus(undefined);
      setThinkingSteps([]);
      setIsThinkingComplete(false);
      setPendingConfirmation(null);
      setFollowUpSuggestions([]);

      // 添加超时保护 — P0 #19: Dynamic timeout with tool_progress reset
      const STREAM_TIMEOUT = 120000; // 120s base timeout (was 60s — too short for multi-tool)
      let streamTimeoutId: ReturnType<typeof setTimeout>;
      const resetStreamTimeout = () => {
        clearTimeout(streamTimeoutId);
        streamTimeoutId = setTimeout(() => {
          if (abortControllerRef.current) {
            abortControllerRef.current.abort();
          }
          setIsTyping(false);
          setAiStatus(undefined);
          toast.error('AI 响应超时（120秒），请简化请求或稍后重试', { duration: 5000 });
        }, STREAM_TIMEOUT);
      };
      resetStreamTimeout();

      // Support both old callback style and new object style
      const onUpdate = typeof callbacks === 'function' ? callbacks : callbacks?.onUpdate;
      const onThinkingStep = typeof callbacks === 'object' ? callbacks.onThinkingStep : undefined;
      const onThinkingComplete =
        typeof callbacks === 'object' ? callbacks.onThinkingComplete : undefined;
      const onToolProgress = typeof callbacks === 'object' ? callbacks.onToolProgress : undefined;
      const onOrchestration = typeof callbacks === 'object' ? callbacks.onOrchestration : undefined;

      const chatMessages: Array<{ role: string; content: string; image_urls?: string[] }> = history
        .filter((m) => m.id !== '1') // Skip greeting
        .map((m) => {
          const msg: { role: string; content: string; image_urls?: string[] } = {
            role: m.role as 'user' | 'assistant',
            content: m.content,
          };
          if (m.imageUrls?.length) msg.image_urls = m.imageUrls;
          return msg;
        });

      const currentMsg: { role: string; content: string; image_urls?: string[] } = {
        role: 'user',
        content: input,
      };
      if (options?.imageUrls?.length) currentMsg.image_urls = options.imageUrls;
      chatMessages.push(currentMsg);

      abortControllerRef.current = new AbortController();

      try {
        // Check network connectivity
        if (!navigator.onLine) {
          throw new Error('网络已断开，请检查网络连接');
        }

        // P0: Secure Identity Verification
        const {
          data: { session },
          error: sessionError,
        } = await supabase.auth.getSession();

        if (sessionError) {
          throw new Error('获取用户会话失败，请重新登录');
        }

        const token = session?.access_token;

        if (!token) {
          throw new Error('请先登录后再使用 AI 助手');
        }

        // ── 3-Tier Fallback Architecture ──
        // Tier 1a: Try Zeabur backend directly
        // Tier 1b: Try Supabase Edge Function proxy → Zeabur backend
        // Tier 2:  Enhanced direct mode (browser → AI provider with business context)

        let tier1Succeeded = false;
        let tier1aRetried = false;

        // ── Tier 1a: Direct backend ──
        try {
          setAiStatus('正在连接后端服务...');
          // Save request context for HITL confirmation resend
          lastRequestRef.current = { messages: chatMessages, agent };
          const response = await fetch(getBackendUrl(), {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              messages: chatMessages,
              agent: agent,
              userId: userId,
              sessionId: sessionIdRef.current,
              system_confirmed: options?.system_confirmed || false,
              confirmed_tool: options?.confirmed_tool || null,
              vmd_agent_code: options?.vmd_agent_code,
              scene_code: options?.scene_code,
            }),
            signal: abortControllerRef.current.signal,
          });

          if (response.ok) {
            setAiStatus(undefined);
            await parseBackendStream(
              response,
              onUpdate,
              onThinkingStep,
              onThinkingComplete,
              onToolProgress,
              onOrchestration,
              resetStreamTimeout
            );
            tier1Succeeded = true;
          } else if (response.status >= 500) {
            // 5xx: backend down, fall through to next tier
          } else if (response.status === 429) {
            // Rate limited — show countdown toast with Retry-After
            const retryAfter = parseInt(response.headers.get('Retry-After') || '60', 10);
            toast.error(`AI 请求频率超限，请 ${retryAfter} 秒后重试`, {
              id: 'ai-rate-limit',
              duration: Math.min(retryAfter * 1000, 30000),
            });
            throw new Error(`请求频率超限，请 ${retryAfter} 秒后重试`);
          } else {
            // 4xx errors are real errors, don't fallback
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `请求失败: ${response.status}`);
          }
        } catch (err) {
          if ((err as Error).name === 'AbortError') throw err;
          const msg = (err as Error).message || '';
          const isNetworkError =
            msg.includes('Failed to fetch') ||
            msg.includes('NetworkError') ||
            msg.includes('network');
          if (!isNetworkError && !msg.includes('500')) {
            throw err; // Non-network error, propagate
          }
          // Retry once before falling through to Tier 1b
          if (!tier1aRetried) {
            tier1aRetried = true;
            try {
              setAiStatus('正在重试连接...');
              await new Promise((r) => setTimeout(r, 1000));
              const retryResponse = await fetch(getBackendUrl(), {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                  messages: chatMessages,
                  agent: agent,
                  userId: userId,
                  sessionId: sessionIdRef.current,
                  system_confirmed: options?.system_confirmed || false,
                  confirmed_tool: options?.confirmed_tool || null,
                  vmd_agent_code: options?.vmd_agent_code,
                  scene_code: options?.scene_code,
                }),
                signal: abortControllerRef.current.signal,
              });
              if (retryResponse.ok) {
                setAiStatus(undefined);
                await parseBackendStream(
                  retryResponse,
                  onUpdate,
                  onThinkingStep,
                  onThinkingComplete,
                  onToolProgress,
                  onOrchestration,
                  resetStreamTimeout
                );
                tier1Succeeded = true;
              }
            } catch (retryErr) {
              if ((retryErr as Error).name === 'AbortError') throw retryErr;
              // Retry failed, fall through to Tier 1b
            }
          }
        }

        if (tier1Succeeded) return;

        // ── Tier 1b: Supabase Edge Function proxy ──
        try {
          setAiStatus('正在通过代理连接...');
          const response = await fetch(getEdgeFunctionUrl(), {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              messages: chatMessages,
              agent: agent,
              userId: userId,
              sessionId: sessionIdRef.current,
            }),
            signal: abortControllerRef.current.signal,
          });

          if (response.ok) {
            setAiStatus(undefined);
            await parseBackendStream(
              response,
              onUpdate,
              onThinkingStep,
              onThinkingComplete,
              onToolProgress,
              onOrchestration,
              resetStreamTimeout
            );
            tier1Succeeded = true;
          } else {
            // Proxy failed, fall through to Tier 2
          }
        } catch (err) {
          if ((err as Error).name === 'AbortError') throw err;
          // Tier 1b failed, fall through to Tier 2
        }

        if (tier1Succeeded) return;

        // ── Tier 2: Enhanced direct mode with business context ──
        if (!ENABLE_BROWSER_AI_PROXY_FALLBACK) {
          throw new Error(
            'AI backend is unavailable. Browser-side AI proxy fallback is disabled by policy.'
          );
        }
        setAiStatus('正在切换到增强直连模式...');
        const success = await attemptEnhancedDirectStream({
          chatMessages,
          signal: abortControllerRef.current.signal,
          onUpdate,
          agent,
          onStatus: setAiStatus,
        });
        if (success) return;

        throw new Error('所有连接模式均失败，请检查设置中心的 AI 配置');
      } catch (error) {
        if ((error as Error).name === 'AbortError') return;

        const err = error as Error;
        let errorMessage = 'AI 回复失败，请重试';

        if (err.message.includes('Failed to fetch')) {
          errorMessage =
            '网络连接失败，所有连接模式均不可用。请检查设置中心的 AI 配置或联系管理员。';
        } else if (err.message.includes('登录') || err.message.includes('会话')) {
          errorMessage = err.message;
        } else if (err.message) {
          errorMessage = err.message;
        }

        toast.error(errorMessage);

        // 关键修复：确保状态重置
        setIsTyping(false);
        setAiStatus(undefined);

        throw error;
      } finally {
        clearTimeout(streamTimeoutId);
        setIsTyping(false);
        setAiStatus(undefined);
      }
    },
    [userId, getBackendUrl, getEdgeFunctionUrl]
  );

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  /** HITL: Resend the last request with system_confirmed=true */
  const confirmAndResend = useCallback(
    async (
      history: AIMessage[],
      callbacks?: StreamCallbacks | ((content: string, id: string) => void),
      modifiedArgs?: Record<string, unknown>
    ) => {
      const lastReq = lastRequestRef.current;
      if (!lastReq) return;

      // Read from ref to avoid depending on pendingConfirmation state
      const confirmation = pendingConfirmationRef.current;
      const toolInfo = confirmation
        ? { tool_name: confirmation.tool_name, args: modifiedArgs || confirmation.args }
        : undefined;
      setPendingConfirmation(null);
      const lastUserMsg = lastReq.messages[lastReq.messages.length - 1]?.content || '';
      // P1-7: If args were modified, append modification note
      const extraContext = modifiedArgs
        ? `\n[用户已修改参数: ${JSON.stringify(modifiedArgs)}]`
        : '';
      await streamChat(lastUserMsg + extraContext, history, lastReq.agent, callbacks, {
        system_confirmed: true,
        confirmed_tool: toolInfo,
      });
    },
    [streamChat]
  );

  /** P1-7: Answer an agent's proactive question */
  const answerQuestion = useCallback(
    async (
      answer: string,
      history: AIMessage[],
      callbacks?: StreamCallbacks | ((content: string, id: string) => void)
    ) => {
      setPendingQuestion(null);
      const lastReq = lastRequestRef.current;
      const agent = lastReq?.agent;
      await streamChat(answer, history, agent, callbacks);
    },
    [streamChat]
  );

  const dismissConfirmation = useCallback(() => setPendingConfirmation(null), []);
  const dismissQuestion = useCallback(() => setPendingQuestion(null), []);
  const clearThinkingSteps = useCallback(() => setThinkingSteps([]), []);

  return {
    isTyping,
    aiStatus,
    thinkingSteps,
    isThinkingComplete,
    pendingConfirmation,
    pendingQuestion,
    circuitBreak,
    quotaInfo,
    followUpSuggestions,
    isOffline,
    streamChat,
    stopStream,
    confirmAndResend,
    answerQuestion,
    dismissConfirmation,
    dismissQuestion,
    clearThinkingSteps,
    dismissCircuitBreak: useCallback(() => setCircuitBreak(null), []),
    sessionId,
    setSessionId,
  };
}

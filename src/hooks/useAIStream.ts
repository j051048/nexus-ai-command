import { getApiBaseUrl } from "@/lib/apiConfig";
import { useState, useRef, useCallback, useEffect } from 'react';
import { AIMessage, ThinkingStep } from '@/types/nexus';
import { toast } from 'sonner';
import { supabase } from '@/integrations/supabase/client';
import { buildSystemPrompt, type UserProfile } from '@/services/agentPrompts';
import { fetchBusinessContext } from '@/services/businessContext';
import { httpClient } from '@/lib/httpClient';

interface UseAIStreamProps {
    userId: string;
    onMessageUpdate?: (messages: AIMessage[]) => void;
}

interface StreamCallbacks {
    onUpdate?: (content: string, id: string) => void;
    onThinkingStep?: (step: ThinkingStep) => void;
    onThinkingComplete?: (totalSteps: number) => void;
    onToolProgress?: (progress: { tool_name: string; status: string; duration_ms?: number }) => void;
    onOrchestration?: (event: Record<string, unknown>) => void;
}

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
    const [sessionId, setSessionId] = useState<string>(`session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
    const sessionIdRef = useRef<string>(sessionId);
    useEffect(() => {
        sessionIdRef.current = sessionId;
    }, [sessionId]);
    const lastRequestRef = useRef<{ messages: Array<{ role: string; content: string }>; agent?: string } | null>(null);
    const pendingConfirmationRef = useRef<ConfirmationRequest | null>(null);
    pendingConfirmationRef.current = pendingConfirmation;

    // ── Weak network degradation: online/offline detection ──
    const [isOffline, setIsOffline] = useState(!navigator.onLine);
    useEffect(() => {
        const handleOffline = () => {
            setIsOffline(true);
            toast.warning('网络已断开，AI 功能暂时不可用', { id: 'network-status', duration: Infinity });
        };
        const handleOnline = () => {
            setIsOffline(false);
            toast.success('网络已恢复', { id: 'network-status', duration: 3000 });
        };
        window.addEventListener('offline', handleOffline);
        window.addEventListener('online', handleOnline);
        return () => {
            window.removeEventListener('offline', handleOffline);
            window.removeEventListener('online', handleOnline);
        };
    }, []);

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
    const parseBackendStream = async (
        response: Response,
        onUpdate?: (content: string, id: string) => void,
        onThinkingStep?: (step: ThinkingStep) => void,
        onThinkingComplete?: (totalSteps: number) => void,
        onToolProgress?: (progress: { tool_name: string; status: string; duration_ms?: number }) => void,
        onOrchestration?: (event: Record<string, unknown>) => void,
        onActivity?: () => void,  // P0 #19: callback to reset stream timeout on activity
    ): Promise<void> => {
        if (!response.body) throw new Error('响应体为空');

        const assistantMsgId = Date.now().toString();

        // Check Content-Type: if not SSE, try to parse as JSON directly
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('text/event-stream') && !contentType.includes('text/plain')) {
            try {
                const json = await response.json();
                const content = json.choices?.[0]?.message?.content
                    || json.choices?.[0]?.delta?.content
                    || json.error?.message
                    || (typeof json.error === 'string' ? json.error : null)
                    || JSON.stringify(json);
                onUpdate?.(content, assistantMsgId);
                return;
            } catch {
                // If JSON parse fails, read as text
                const text = await response.text();
                if (text) onUpdate?.(text, assistantMsgId);
                return;
            }
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let textBuffer = '';
        let assistantContent = '';
        let streamDone = false;

        // P1 Fix: RAF 节流 — 累积 token 后按帧批量刷新，避免每个 token 触发一次 re-render
        let rafPending = false;
        let rafId = 0;
        let lastFlushedContent = '';
        const flushContent = () => {
            rafPending = false;
            if (assistantContent !== lastFlushedContent) {
                lastFlushedContent = assistantContent;
                onUpdate?.(assistantContent, assistantMsgId);
            }
        };
        const scheduleFlush = () => {
            if (!rafPending) {
                rafPending = true;
                rafId = requestAnimationFrame(flushContent);
            }
        };

        while (true) {
            let readResult: ReadableStreamReadResult<Uint8Array>;
            try {
                readResult = await reader.read();
            } catch (readErr) {
                // Stream interrupted mid-response (network flicker, server disconnect)
                if (assistantContent) {
                    if (rafPending) {
                        cancelAnimationFrame(rafId);
                        flushContent();
                    }
                    assistantContent += '\n\n⚠️ 网络中断，回复可能不完整。请检查网络后重试。';
                    onUpdate?.(assistantContent, assistantMsgId);
                }
                throw readErr;
            }
            const { done, value } = readResult;
            if (done) break;

            textBuffer += decoder.decode(value, { stream: true });

            let newlineIndex: number;
            while ((newlineIndex = textBuffer.indexOf('\n')) !== -1) {
                let line = textBuffer.slice(0, newlineIndex);
                textBuffer = textBuffer.slice(newlineIndex + 1);

                if (line.endsWith('\r')) line = line.slice(0, -1);
                if (line.startsWith(':') || line.trim() === '') continue;
                if (!line.startsWith('data: ')) continue;

                const jsonStr = line.slice(6).trim();
                if (jsonStr === '[DONE]') {
                    streamDone = true;
                    break;
                }

                try {
                    const parsed = JSON.parse(jsonStr);
                    const content = parsed.choices?.[0]?.delta?.content as string | undefined;

                    // Handle thinking step events
                    if (parsed.thinking_step) {
                        const step = parsed.thinking_step as ThinkingStep;
                        setThinkingSteps(prev => [...prev, step]);
                        onThinkingStep?.(step);
                        continue;
                    }

                    // Handle thinking chain completion
                    if (parsed.thinking_chain_complete) {
                        setIsThinkingComplete(true);
                        onThinkingComplete?.(parsed.total_steps || 0);
                        continue;
                    }

                    if (parsed.status) {
                        setAiStatus(parsed.status);
                        continue;
                    }

                    // Handle HITL confirmation request from blocked tool calls
                    if (parsed.confirmation_required) {
                        setPendingConfirmation(parsed.confirmation_required as ConfirmationRequest);
                        continue;
                    }

                    // P1-7: Handle ask_user events from agent proactive questioning
                    if (parsed.ask_user) {
                        setPendingQuestion(parsed.ask_user as AskUserRequest);
                        continue;
                    }

                    // Handle circuit break events (loop detection / max iterations)
                    if (parsed.circuit_break) {
                        setCircuitBreak(parsed.circuit_break as CircuitBreakInfo);
                        continue;
                    }

                    // Handle tool execution progress events
                    if (parsed.tool_progress) {
                        onToolProgress?.(parsed.tool_progress);
                        onActivity?.();  // P0 #19: reset timeout — tool is actively running
                        continue;
                    }

                    // Handle sanitized content correction from backend
                    if (parsed.sanitized_content) {
                        assistantContent = parsed.sanitized_content;
                        scheduleFlush();
                        continue;
                    }

                    // Handle quota info from backend (emitted after each request)
                    if (parsed.quota) {
                        setQuotaInfo(parsed.quota as QuotaInfo);
                        continue;
                    }

                    // P2-13: Handle follow-up suggestions
                    if (parsed.follow_up_suggestions) {
                        setFollowUpSuggestions(parsed.follow_up_suggestions as string[]);
                        continue;
                    }

                    // P2-10: Handle orchestration events
                    if (parsed.orchestration) {
                        onOrchestration?.(parsed.orchestration as Record<string, unknown>);
                        continue;
                    }

                    if (content) {
                        setAiStatus(undefined);
                        assistantContent += content;
                        scheduleFlush();
                        onActivity?.();  // P0 #19: reset timeout on content received
                    }
                } catch {
                    // JSON incomplete — re-buffer and wait for next chunk
                    textBuffer = line + '\n' + textBuffer;
                    break;
                }
            }

            if (streamDone) break;
        }

        // P1 Fix: 流结束后立即刷新剩余累积内容，确保最后一批 token 显示到 UI
        if (rafPending) {
            cancelAnimationFrame(rafId); // cancel any pending RAF
            flushContent();
        } else if (assistantContent !== lastFlushedContent) {
            flushContent();
        }

        // Safety net: if stream ended but we got no content, check remaining buffer
        if (!assistantContent && textBuffer.trim()) {
            try {
                // Attempt to parse leftover as JSON (non-SSE fallback)
                const json = JSON.parse(textBuffer.trim());
                const content = json.choices?.[0]?.message?.content
                    || json.choices?.[0]?.delta?.content
                    || json.error?.message
                    || '';
                if (content) onUpdate?.(content, assistantMsgId);
            } catch {
                // Last resort: show trimmed raw text if it looks like content
                const cleaned = textBuffer.trim();
                if (cleaned && !cleaned.startsWith('data: ')) {
                    onUpdate?.(cleaned, assistantMsgId);
                }
            }
        }
    };

    /**
     * Tier 2: Enhanced direct stream with business context.
     * Fetches user profile + business data from Supabase, builds a rich system
     * prompt, then streams from the AI provider directly.
     */
    const attemptEnhancedDirectStream = async (
        chatMessages: Array<{ role: string; content: string }>,
        signal: AbortSignal,
        onUpdate?: (content: string, id: string) => void,
        agent?: string,
    ): Promise<boolean> => {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return false;

        // Fetch user profile via httpClient + AI settings via supabase in parallel
        const [profileResponse, settingsResult] = await Promise.all([
            httpClient.get('/api/users/profile'),
            (async () => {
                // Get org_id first for settings lookup
                const profileResp = await httpClient.get('/api/users/profile');
                const orgId = profileResp.data?.data?.user?.organization_id;
                let query = supabase
                    .from('ai_settings')
                    .select('base_url, api_key, model')
                    .eq('user_id', user.id);
                if (orgId) {
                    query = query.eq('organization_id', orgId);
                }
                return query.maybeSingle();
            })(),
        ]);

        const profile = profileResponse.data?.data?.user;
        const aiSettings = settingsResult.data as Record<string, unknown> | null;

        if (!aiSettings?.api_key || !aiSettings?.base_url) {
            throw new Error('请先在设置中心配置 AI API Key 和 Base URL');
        }

        // Build user profile for prompt
        const userProfile: UserProfile = {
            fullName: profile?.full_name || '未知用户',
            role: profile?.role || 'employee',
            department: profile?.department || undefined,
            jobTitle: profile?.job_title || undefined,
        };

        // Fetch business context from Supabase
        setAiStatus('正在加载业务数据...');
        const businessContext = await fetchBusinessContext(
            agent,
            user.id,
            userProfile.role,
        );

        // Build the full system prompt with persona + user context + business data
        const systemPrompt = buildSystemPrompt(agent, userProfile, businessContext);

        // Prepend system message to chat
        const messagesWithContext: Array<{ role: string; content: string }> = [
            { role: 'system', content: systemPrompt },
            ...chatMessages,
        ];

        // Build the chat/completions endpoint URL
        let url = aiSettings.base_url.replace(/\/$/, '');
        if (url.endsWith('/chat/completions')) {
            // Already a full endpoint
        } else if (url.endsWith('/v1')) {
            url += '/chat/completions';
        } else {
            url += '/v1/chat/completions';
        }

        setAiStatus('正在连接 AI 服务...');
        // P0 Security Fix: Never send API keys from the browser.
        // Route through backend proxy which holds the key server-side.
        const API_BASE = getApiBaseUrl();
        const proxyUrl = `${API_BASE}/api/chat/proxy`;
        const { data: { session } } = await supabase.auth.getSession();
        const response = await fetch(proxyUrl, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${session?.access_token || ''}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: aiSettings.model || 'gemini-3-flash-preview',
                messages: messagesWithContext,
                stream: true,
            }),
            signal,
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => '');
            throw new Error(`AI 服务错误 (${response.status}): ${errorText.slice(0, 100) || '未知错误'}`);
        }

        if (!response.body) return false;

        setAiStatus(undefined);
        toast.info('已切换到增强直连模式（含业务数据）');

        // Parse OpenAI-compatible SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let textBuffer = '';
        let assistantContent = '';
        const assistantMsgId = Date.now().toString();
        let streamDone = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            textBuffer += decoder.decode(value, { stream: true });

            let newlineIndex: number;
            while ((newlineIndex = textBuffer.indexOf('\n')) !== -1) {
                let line = textBuffer.slice(0, newlineIndex);
                textBuffer = textBuffer.slice(newlineIndex + 1);

                if (line.endsWith('\r')) line = line.slice(0, -1);
                if (line.startsWith(':') || line.trim() === '') continue;
                if (!line.startsWith('data: ')) continue;

                const jsonStr = line.slice(6).trim();
                if (jsonStr === '[DONE]') {
                    streamDone = true;
                    break;
                }

                try {
                    const parsed = JSON.parse(jsonStr);
                    const content = parsed.choices?.[0]?.delta?.content as string | undefined;
                    if (content) {
                        assistantContent += content;
                        onUpdate?.(assistantContent, assistantMsgId);
                    }
                } catch {
                    textBuffer = line + '\n' + textBuffer;
                    break;
                }
            }

            if (streamDone) break;
        }
        return true;
    };

    const streamChat = useCallback(async (
        input: string,
        history: AIMessage[],
        agent?: string,
        callbacks?: StreamCallbacks | ((content: string, id: string) => void),
        options?: { system_confirmed?: boolean; confirmed_tool?: { tool_name: string; args: Record<string, unknown> }; vmd_agent_code?: string; scene_code?: string; imageUrls?: string[] }
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
        const onThinkingComplete = typeof callbacks === 'object' ? callbacks.onThinkingComplete : undefined;
        const onToolProgress = typeof callbacks === 'object' ? callbacks.onToolProgress : undefined;
        const onOrchestration = typeof callbacks === 'object' ? callbacks.onOrchestration : undefined;

        const chatMessages: Array<{ role: string; content: string; image_urls?: string[] }> = history
            .filter(m => m.id !== '1') // Skip greeting
            .map(m => {
                const msg: { role: string; content: string; image_urls?: string[] } = {
                    role: m.role as 'user' | 'assistant',
                    content: m.content,
                };
                if (m.imageUrls?.length) msg.image_urls = m.imageUrls;
                return msg;
            });

        const currentMsg: { role: string; content: string; image_urls?: string[] } = { role: 'user', content: input };
        if (options?.imageUrls?.length) currentMsg.image_urls = options.imageUrls;
        chatMessages.push(currentMsg);

        abortControllerRef.current = new AbortController();

        try {
            // Check network connectivity
            if (!navigator.onLine) {
                throw new Error('网络已断开，请检查网络连接');
            }

            // P0: Secure Identity Verification
            const { data: { session }, error: sessionError } = await supabase.auth.getSession();

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
                        'Authorization': `Bearer ${token}`,
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
                    await parseBackendStream(response, onUpdate, onThinkingStep, onThinkingComplete, onToolProgress, onOrchestration, resetStreamTimeout);
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
                const isNetworkError = msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('network');
                if (!isNetworkError && !msg.includes('500')) {
                    throw err; // Non-network error, propagate
                }
                // Retry once before falling through to Tier 1b
                if (!tier1aRetried) {
                    tier1aRetried = true;
                    try {
                        setAiStatus('正在重试连接...');
                        await new Promise(r => setTimeout(r, 1000));
                        const retryResponse = await fetch(getBackendUrl(), {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${token}`,
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
                            await parseBackendStream(retryResponse, onUpdate, onThinkingStep, onThinkingComplete, onToolProgress, onOrchestration, resetStreamTimeout);
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
                        'Authorization': `Bearer ${token}`,
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
                    await parseBackendStream(response, onUpdate, onThinkingStep, onThinkingComplete, onToolProgress, onOrchestration, resetStreamTimeout);
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
            setAiStatus('正在切换到增强直连模式...');
            const success = await attemptEnhancedDirectStream(
                chatMessages,
                abortControllerRef.current.signal,
                onUpdate,
                agent,
            );
            if (success) return;

            throw new Error('所有连接模式均失败，请检查设置中心的 AI 配置');
        } catch (error) {
            if ((error as Error).name === 'AbortError') return;

            const err = error as Error;
            let errorMessage = 'AI 回复失败，请重试';

            if (err.message.includes('Failed to fetch')) {
                errorMessage = '网络连接失败，所有连接模式均不可用。请检查设置中心的 AI 配置或联系管理员。';
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
    }, [userId, getBackendUrl, getEdgeFunctionUrl]);

    const stopStream = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
    }, []);

    /** HITL: Resend the last request with system_confirmed=true */
    const confirmAndResend = useCallback(async (
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
    }, [streamChat]);

    /** P1-7: Answer an agent's proactive question */
    const answerQuestion = useCallback(async (
        answer: string,
        history: AIMessage[],
        callbacks?: StreamCallbacks | ((content: string, id: string) => void)
    ) => {
        setPendingQuestion(null);
        const lastReq = lastRequestRef.current;
        const agent = lastReq?.agent;
        await streamChat(answer, history, agent, callbacks);
    }, [streamChat]);

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

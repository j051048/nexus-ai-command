import { useState, useRef, useCallback } from 'react';
import { AIMessage, ThinkingStep } from '@/types/nexus';
import { toast } from 'sonner';
import { supabase } from '@/integrations/supabase/client';
import { buildSystemPrompt, type UserProfile } from '@/services/agentPrompts';
import { fetchBusinessContext } from '@/services/businessContext';

interface UseAIStreamProps {
    userId: string;
    onMessageUpdate?: (messages: AIMessage[]) => void;
}

interface StreamCallbacks {
    onUpdate?: (content: string, id: string) => void;
    onThinkingStep?: (step: ThinkingStep) => void;
    onThinkingComplete?: (totalSteps: number) => void;
}

export function useAIStream({ userId }: UseAIStreamProps) {
    const [isTyping, setIsTyping] = useState(false);
    const [aiStatus, setAiStatus] = useState<string | undefined>();
    const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
    const [isThinkingComplete, setIsThinkingComplete] = useState(false);
    const abortControllerRef = useRef<AbortController | null>(null);

    /** Tier 1 primary: Zeabur backend directly */
    const getBackendUrl = useCallback(() => {
        let url = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';
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
        const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://hztpazmuejgbtixihcgj.supabase.co';
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
    ): Promise<void> => {
        if (!response.body) throw new Error('No response body');

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

                    // Handle sanitized content correction from backend
                    if (parsed.sanitized_content) {
                        assistantContent = parsed.sanitized_content;
                        onUpdate?.(assistantContent, assistantMsgId);
                        continue;
                    }

                    if (content) {
                        setAiStatus(undefined);
                        assistantContent += content;
                        onUpdate?.(assistantContent, assistantMsgId);
                    }
                } catch {
                    // JSON incomplete — re-buffer and wait for next chunk
                    textBuffer = line + '\n' + textBuffer;
                    break;
                }
            }

            if (streamDone) break;
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

        // Fetch user profile + AI settings in parallel
        const [profileResult, settingsResult] = await Promise.all([
            supabase
                .from('users')
                .select('organization_id, full_name, role, department, job_title')
                .eq('id', user.id)
                .maybeSingle(),
            (() => {
                // Need org_id for settings lookup — do a chained query
                return supabase
                    .from('users')
                    .select('organization_id')
                    .eq('id', user.id)
                    .maybeSingle()
                    .then(({ data: profile }) => {
                        let query = supabase
                            .from('ai_settings')
                            .select('base_url, api_key, model')
                            .eq('user_id', user.id);
                        if (profile?.organization_id) {
                            query = query.eq('organization_id', profile.organization_id);
                        }
                        return query.maybeSingle();
                    });
            })(),
        ]);

        const profile = profileResult.data;
        const aiSettings = settingsResult.data;

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
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${aiSettings.api_key}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: aiSettings.model || 'gpt-4o',
                messages: messagesWithContext,
                stream: true,
            }),
            signal,
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => '');
            throw new Error(`AI 服务错误 (${response.status}): ${errorText.slice(0, 200)}`);
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

    const streamChat = async (
        input: string,
        history: AIMessage[],
        agent?: string,
        callbacks?: StreamCallbacks | ((content: string, id: string) => void)
    ) => {
        setIsTyping(true);
        setAiStatus(undefined);
        setThinkingSteps([]);
        setIsThinkingComplete(false);

        // Support both old callback style and new object style
        const onUpdate = typeof callbacks === 'function' ? callbacks : callbacks?.onUpdate;
        const onThinkingStep = typeof callbacks === 'object' ? callbacks.onThinkingStep : undefined;
        const onThinkingComplete = typeof callbacks === 'object' ? callbacks.onThinkingComplete : undefined;

        const chatMessages = history
            .filter(m => m.id !== '1') // Skip greeting
            .map(m => ({
                role: m.role as 'user' | 'assistant',
                content: m.content,
            }));

        chatMessages.push({ role: 'user', content: input });

        abortControllerRef.current = new AbortController();

        try {
            // Check network connectivity
            if (!navigator.onLine) {
                throw new Error('网络已断开，请检查网络连接');
            }

            // P0: Secure Identity Verification
            const { data: { session }, error: sessionError } = await supabase.auth.getSession();

            if (sessionError) {
                console.error('Session error:', sessionError);
                throw new Error('获取用户会话失败，请重新登录');
            }

            const token = session?.access_token;

            if (!token) {
                console.warn('No auth token available, user may not be logged in');
                throw new Error('请先登录后再使用 AI 助手');
            }

            // ── 3-Tier Fallback Architecture ──
            // Tier 1a: Try Zeabur backend directly
            // Tier 1b: Try Supabase Edge Function proxy → Zeabur backend
            // Tier 2:  Enhanced direct mode (browser → AI provider with business context)

            let tier1Succeeded = false;

            // ── Tier 1a: Direct backend ──
            try {
                setAiStatus('正在连接后端服务...');
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
                    }),
                    signal: abortControllerRef.current.signal,
                });

                if (response.ok) {
                    setAiStatus(undefined);
                    await parseBackendStream(response, onUpdate, onThinkingStep, onThinkingComplete);
                    tier1Succeeded = true;
                } else if (response.status >= 500) {
                    console.warn(`Backend returned ${response.status}, trying Edge Function proxy...`);
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
                console.warn('Tier 1a (direct backend) failed:', msg);
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
                    }),
                    signal: abortControllerRef.current.signal,
                });

                if (response.ok) {
                    setAiStatus(undefined);
                    await parseBackendStream(response, onUpdate, onThinkingStep, onThinkingComplete);
                    tier1Succeeded = true;
                } else {
                    console.warn(`Edge Function proxy returned ${response.status}, falling back to enhanced direct mode...`);
                }
            } catch (err) {
                if ((err as Error).name === 'AbortError') throw err;
                console.warn('Tier 1b (Edge Function proxy) failed:', (err as Error).message);
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
            console.error('AI chat error:', err);

            let errorMessage = 'AI 回复失败，请重试';

            if (err.message.includes('Failed to fetch')) {
                errorMessage = '网络连接失败，所有连接模式均不可用。请检查设置中心的 AI 配置或联系管理员。';
            } else if (err.message.includes('登录') || err.message.includes('会话')) {
                errorMessage = err.message;
            } else if (err.message) {
                errorMessage = err.message;
            }

            toast.error(errorMessage);
            throw error;
        } finally {
            setIsTyping(false);
            setAiStatus(undefined);
        }
    };

    const stopStream = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
    };

    return {
        isTyping,
        aiStatus,
        thinkingSteps,
        isThinkingComplete,
        streamChat,
        stopStream,
        clearThinkingSteps: () => setThinkingSteps([])
    };
}

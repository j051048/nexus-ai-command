import { useState, useRef, useCallback } from 'react';
import { AIMessage, ThinkingStep } from '@/types/nexus';
import { toast } from 'sonner';
import { supabase } from '@/integrations/supabase/client';

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

    const getApiUrl = useCallback(() => {
        let url = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';
        if (!url.startsWith('http')) {
            url = `https://${url}`;
        }
        if (url.endsWith('/')) {
            url = url.slice(0, -1);
        }
        return `${url}/api/chat`;
    }, []);

    /**
     * Fallback: stream directly from AI provider when backend is unavailable.
     * Reads AI settings (base_url, api_key, model) from Supabase and calls
     * the OpenAI-compatible endpoint directly from the browser.
     */
    const attemptDirectStream = async (
        chatMessages: Array<{ role: string; content: string }>,
        signal: AbortSignal,
        onUpdate?: (content: string, id: string) => void,
    ): Promise<boolean> => {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return false;

        // Get user's organization_id for correct settings lookup
        const { data: profileData } = await supabase
            .from('users')
            .select('organization_id')
            .eq('id', user.id)
            .maybeSingle();

        const orgFilter = profileData?.organization_id;

        // Load AI settings from Supabase
        let query = supabase
            .from('ai_settings')
            .select('base_url, api_key, model')
            .eq('user_id', user.id);

        if (orgFilter) {
            query = query.eq('organization_id', orgFilter);
        }

        const { data: aiSettings } = await query.maybeSingle();

        if (!aiSettings?.api_key || !aiSettings?.base_url) {
            throw new Error('请先在设置中心配置 AI API Key 和 Base URL');
        }

        // Build the chat/completions endpoint URL
        let url = aiSettings.base_url.replace(/\/$/, '');
        if (url.endsWith('/chat/completions')) {
            // Already a full endpoint, use as-is
        } else if (url.endsWith('/v1')) {
            url += '/chat/completions';
        } else {
            url += '/v1/chat/completions';
        }

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${aiSettings.api_key}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: aiSettings.model || 'gpt-4o',
                messages: chatMessages,
                stream: true,
            }),
            signal,
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => '');
            throw new Error(`AI 服务错误 (${response.status}): ${errorText.slice(0, 200)}`);
        }

        if (!response.body) return false;

        toast.info('后端暂不可用，已切换到直连模式');

        // Parse OpenAI-compatible SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let textBuffer = '';
        let assistantContent = '';
        const assistantMsgId = Date.now().toString();

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
                if (jsonStr === '[DONE]') return true;

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

            // Try backend first; fall back to direct AI provider if unreachable
            let backendFailed = false;

            try {
                const response = await fetch(getApiUrl(), {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        messages: chatMessages,
                        agent: agent,
                        userId: userId
                    }),
                    signal: abortControllerRef.current.signal,
                });

                if (!response.ok) {
                    // Backend returned server error — try direct mode
                    if (response.status >= 500) {
                        console.warn(`Backend returned ${response.status}, switching to direct mode`);
                        backendFailed = true;
                    } else {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.error || `请求失败: ${response.status}`);
                    }
                }

                if (!backendFailed) {
                    if (!response.body) throw new Error('No response body');

                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let textBuffer = '';
                    let assistantContent = '';
                    const assistantMsgId = Date.now().toString();

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
                            if (jsonStr === '[DONE]') break;

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

                                // Handle sanitized content correction from backend (#12 fix)
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
                                textBuffer = line + '\n' + textBuffer;
                                break;
                            }
                        }
                    }
                    return; // Backend stream succeeded
                }
            } catch (backendErr) {
                if ((backendErr as Error).name === 'AbortError') throw backendErr;
                const msg = (backendErr as Error).message || '';
                if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('network')) {
                    console.warn('Backend unreachable, switching to direct mode:', msg);
                    backendFailed = true;
                } else {
                    throw backendErr; // Non-network error, propagate
                }
            }

            // Fallback: direct stream to AI provider
            if (backendFailed) {
                setAiStatus('正在切换到直连模式...');
                const success = await attemptDirectStream(
                    chatMessages,
                    abortControllerRef.current.signal,
                    onUpdate,
                );
                if (success) return;
                throw new Error('直连 AI 服务也失败了，请检查设置中心的 API 配置');
            }
        } catch (error) {
            if ((error as Error).name === 'AbortError') return;

            const err = error as Error;
            console.error('AI chat error:', err);

            // Provide more specific error messages
            let errorMessage = 'AI 回复失败，请重试';

            if (err.message.includes('Failed to fetch')) {
                errorMessage = '网络连接失败，后端和直连模式均不可用。请检查设置中心的 AI 配置或联系管理员。';
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

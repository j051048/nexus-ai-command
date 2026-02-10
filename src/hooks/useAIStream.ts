import { useState, useRef, useCallback } from 'react';
import { AIMessage } from '@/types/nexus';
import { toast } from 'sonner';
import { supabase } from '@/integrations/supabase/client';

interface UseAIStreamProps {
    userId: string;
    onMessageUpdate?: (messages: AIMessage[]) => void;
}

export function useAIStream({ userId }: UseAIStreamProps) {
    const [isTyping, setIsTyping] = useState(false);
    const [aiStatus, setAiStatus] = useState<string | undefined>();
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

    const streamChat = async (
        input: string,
        history: AIMessage[],
        agent?: string,
        onUpdate?: (content: string, id: string) => void
    ) => {
        setIsTyping(true);
        setAiStatus(undefined);

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
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `请求失败: ${response.status}`);
            }

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
        } catch (error) {
            if ((error as Error).name === 'AbortError') return;
            
            const err = error as Error;
            console.error('AI chat error:', err);
            
            // Provide more specific error messages
            let errorMessage = 'AI 回复失败，请重试';
            
            if (err.message.includes('Failed to fetch')) {
                errorMessage = '网络连接失败，请检查网络或稍后重试';
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
        streamChat,
        stopStream
    };
}

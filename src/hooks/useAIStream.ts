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
            // P0: Secure Identity Verification
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;

            const response = await fetch(getApiUrl(), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token ? `Bearer ${token}` : `test:${userId}` // Fallback for dev only
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
            console.error('AI chat error:', error);
            toast.error((error as Error).message || 'AI 回复失败，请重试');
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

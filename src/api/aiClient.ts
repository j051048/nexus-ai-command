import { supabase } from '@/integrations/supabase/client';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';

interface RequestOptions extends RequestInit {
    requireAuth?: boolean;
}

export const aiClient = {
    async fetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
        let url = API_BASE_URL;
        if (!url.startsWith('http')) {
            // If it looks like localhost but no protocol
            if (url.includes('localhost')) {
                url = `http://${url}`;
            } else {
                url = `https://${url}`;
            }
        }

        // Ensure no double slash
        const cleanBase = url.replace(/\/$/, '');
        const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
        const fullUrl = `${cleanBase}/${cleanEndpoint}`;

        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            ...(options.headers as Record<string, string>),
        };

        if (options.requireAuth !== false) {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
        }

        const response = await fetch(fullUrl, {
            ...options,
            headers,
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => response.statusText);
            throw new Error(`API Request Failed (${response.status}): ${errorText}`);
        }

        return response.json();
    },

    /**
     * Submit an approval request to the AI Orchestration Layer
     */
    async processApproval(data: { requester_id: string; type: string; amount: number; details: string }) {
        return this.fetch('api/approval/process', {
            method: 'POST',
            body: JSON.stringify(data)
        }) as Promise<{ decision: string; reason: string }>;
    },

    /**
     * Generic chat completion
     */
    async chat(messages: { role: string; content: string; [key: string]: unknown }[], model: string = 'gpt-4o') {
        // NOTE: This endpoint might return a stream, so generic fetch wrapper might need adjustment for streams.
        // But for simple request/response:
        return this.fetch('api/chat', {
            method: 'POST',
            body: JSON.stringify({ messages, model })
        });
    }
};

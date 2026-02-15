import { supabase } from '@/integrations/supabase/client';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';

interface RequestOptions extends RequestInit {
    requireAuth?: boolean;
    _retried?: boolean; // internal flag to prevent infinite retry
}

async function getAuthToken(): Promise<string | null> {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
}

async function refreshAndGetToken(): Promise<string | null> {
    const { data: { session }, error } = await supabase.auth.refreshSession();
    if (error || !session) {
        // Refresh failed — session is dead, force sign out
        await supabase.auth.signOut();
        window.location.href = '/login';
        return null;
    }
    return session.access_token;
}

function buildUrl(endpoint: string): string {
    let url = API_BASE_URL;
    if (!url.startsWith('http')) {
        url = url.includes('localhost') ? `http://${url}` : `https://${url}`;
    }
    const cleanBase = url.replace(/\/$/, '');
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
    return `${cleanBase}/${cleanEndpoint}`;
}

export const aiClient = {
    async fetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
        const fullUrl = buildUrl(endpoint);

        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            ...(options.headers as Record<string, string>),
        };

        if (options.requireAuth !== false) {
            const token = await getAuthToken();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
        }

        const response = await fetch(fullUrl, {
            ...options,
            headers,
        });

        // Handle 401: try refresh token once then retry
        if (response.status === 401 && !options._retried && options.requireAuth !== false) {
            const newToken = await refreshAndGetToken();
            if (newToken) {
                return this.fetch<T>(endpoint, {
                    ...options,
                    _retried: true,
                    headers: {
                        ...(options.headers as Record<string, string>),
                        'Authorization': `Bearer ${newToken}`,
                    },
                });
            }
            // refreshAndGetToken already redirected to /login
            throw new Error('会话已过期，请重新登录');
        }

        if (!response.ok) {
            let errorMessage = `API Request Failed (${response.status})`;
            try {
                const errorData = await response.json();
                if (errorData.error && errorData.error.message) {
                    errorMessage = errorData.error.message;
                } else if (errorData.detail) {
                    if (typeof errorData.detail === 'string') {
                        errorMessage = errorData.detail;
                    } else if (Array.isArray(errorData.detail)) {
                         // eslint-disable-next-line @typescript-eslint/no-explicit-any
                         errorMessage = errorData.detail.map((d: any) => d.msg).join(', ');
                    }
                }
            } catch {
                const text = await response.text().catch(() => response.statusText);
                 errorMessage += `: ${text.slice(0, 100)}`;
            }
            throw new Error(errorMessage);
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
        return this.fetch('api/chat', {
            method: 'POST',
            body: JSON.stringify({ messages, model })
        });
    }
};

import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// --- Distributed Trace ID ---
// Generate a unique trace ID per browser tab/session for end-to-end tracing.
// This ID is sent as X-Trace-ID header and can be correlated across
// frontend logs → API middleware → database audit logs.
function generateTraceId(): string {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substring(2, 10);
    return `fe-${timestamp}-${random}`;
}

let _sessionTracePrefix = generateTraceId();

/** Get a trace ID for the current operation (unique per API call, prefixed with session) */
export function getTraceId(): string {
    const seq = Math.random().toString(36).substring(2, 6);
    return `${_sessionTracePrefix}-${seq}`;
}

/** Reset session trace prefix (e.g., on login/logout) */
export function resetTraceSession(): void {
    _sessionTracePrefix = generateTraceId();
}

interface RequestOptions extends RequestInit {
    requireAuth?: boolean;
    _retried?: boolean; // internal flag to prevent infinite retry
    /** Skip the unified error toast (caller handles errors manually) */
    _silentError?: boolean;
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

// ─── Unified Error Interceptor ──────────────────────────────
// Centralized error handler that shows user-friendly toasts
// for common HTTP error codes and network failures.

function handleErrorResponse(status: number, errorMessage: string, silent?: boolean): void {
    if (silent) return;

    switch (status) {
        case 401:
            toast.error('会话已过期，请重新登录', {
                id: 'auth-expired', // deduplicate
                action: {
                    label: '去登录',
                    onClick: () => { window.location.href = '/login'; },
                },
            });
            break;
        case 403:
            toast.error('没有权限执行此操作', { id: 'no-permission' });
            break;
        case 500:
        case 502:
        case 503:
        case 504:
            toast.error('服务器错误，请稍后重试', { id: 'server-error' });
            break;
        case 422:
            // Validation error — show the specific message
            toast.error(errorMessage || '请求参数有误');
            break;
        case 429:
            toast.error('请求过于频繁，请稍后再试', { id: 'rate-limit' });
            break;
        default:
            // For other 4xx/5xx, show the extracted message
            if (status >= 400) {
                toast.error(errorMessage || `请求失败 (${status})`);
            }
            break;
    }
}

function handleNetworkError(error: Error, silent?: boolean): void {
    if (silent) return;

    const msg = error.message || '';
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('network')) {
        toast.error('网络不可用，请检查网络连接', { id: 'network-error' });
    } else if (msg.includes('AbortError') || error.name === 'AbortError') {
        // User-initiated abort — no toast
    } else {
        toast.error(msg || '请求失败，请重试');
    }
}

export const aiClient = {
    async fetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
        const fullUrl = buildUrl(endpoint);
        const silent = options._silentError;

        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            'X-Trace-ID': getTraceId(),
            ...(options.headers as Record<string, string>),
        };

        if (options.requireAuth !== false) {
            const token = await getAuthToken();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
        }

        let response: Response;
        try {
            response = await fetch(fullUrl, {
                ...options,
                headers,
            });
        } catch (networkError) {
            // Network-level failure (no response at all)
            handleNetworkError(networkError as Error, silent);
            throw networkError;
        }

        // Handle 401: try refresh token once then retry
        if (response.status === 401 && !options._retried && options.requireAuth !== false) {
            const newToken = await refreshAndGetToken();
            if (newToken) {
                return this.fetch(endpoint, {
                    ...options,
                    _retried: true,
                    headers: {
                        ...(options.headers as Record<string, string>),
                        'Authorization': `Bearer ${newToken}`,
                    },
                });
            }
            // refreshAndGetToken already redirected to /login
            handleErrorResponse(401, '会话已过期，请重新登录', silent);
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
                         errorMessage = errorData.detail.map((d: { msg: string }) => d.msg).join(', ');
                    }
                }
            } catch {
                const text = await response.text().catch(() => response.statusText);
                 errorMessage += `: ${text.slice(0, 100)}`;
            }

            // Unified error interceptor toast
            handleErrorResponse(response.status, errorMessage, silent);
            throw new Error(errorMessage);
        }

        return response.json();
    },

    /** GET convenience */
    async get<T = unknown>(endpoint: string, options: RequestOptions = {}): Promise<{ data: T }> {
        const data = await this.fetch(endpoint, { ...options, method: 'GET' });
        return { data };
    },

    /** POST convenience */
    async post<T = unknown>(endpoint: string, body?: unknown, options: RequestOptions = {}): Promise<{ data: T }> {
        const data = await this.fetch(endpoint, {
            ...options,
            method: 'POST',
            body: body ? JSON.stringify(body) : undefined,
        });
        return { data };
    },

    /** PUT convenience */
    async put<T = unknown>(endpoint: string, body?: unknown, options: RequestOptions = {}): Promise<{ data: T }> {
        const data = await this.fetch(endpoint, {
            ...options,
            method: 'PUT',
            body: body ? JSON.stringify(body) : undefined,
        });
        return { data };
    },

    /** DELETE convenience */
    async delete<T = unknown>(endpoint: string, options: RequestOptions = {}): Promise<{ data: T }> {
        const data = await this.fetch(endpoint, { ...options, method: 'DELETE' });
        return { data };
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
    },

    /**
     * Upload audio for STT transcription (multipart/form-data)
     */
    async uploadAudio(audioBlob: Blob, mimeType: string): Promise<{ data: { text: string; empty?: boolean } }> {
        const fullUrl = buildUrl('api/audio/transcribe');

        const ext = mimeType.includes('wav') ? '.wav'
            : mimeType.includes('mp4') ? '.m4a'
            : mimeType.includes('mp3') ? '.mp3'
            : '.webm';
        const formData = new FormData();
        formData.append('file', audioBlob, `recording${ext}`);

        const headers: Record<string, string> = {
            'X-Trace-ID': getTraceId(),
        };

        const token = await getAuthToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        let response: Response;
        try {
            response = await fetch(fullUrl, {
                method: 'POST',
                headers,
                body: formData,
            });
        } catch (networkError) {
            handleNetworkError(networkError as Error);
            throw networkError;
        }

        if (!response.ok) {
            let errorMessage = `语音识别失败 (${response.status})`;
            try {
                const errorData = await response.json();
                if (errorData.error?.message) {
                    errorMessage = errorData.error.message;
                } else if (errorData.detail) {
                    errorMessage = typeof errorData.detail === 'string'
                        ? errorData.detail
                        : JSON.stringify(errorData.detail);
                }
            } catch {
                // ignore parse error
            }
            handleErrorResponse(response.status, errorMessage);
            throw new Error(errorMessage);
        }

        return response.json();
    }
};

import { toast } from 'sonner';

import { supabase } from '@/integrations/supabase/client';
import { getApiBaseUrl } from '@/lib/apiConfig';

const API_BASE_URL = getApiBaseUrl();

function generateTraceId(): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).slice(2, 10);
  return `fe-${timestamp}-${random}`;
}

let sessionTracePrefix = generateTraceId();

export function getTraceId(): string {
  const seq = Math.random().toString(36).slice(2, 6);
  return `${sessionTracePrefix}-${seq}`;
}

export function resetTraceSession(): void {
  sessionTracePrefix = generateTraceId();
}

interface RequestOptions extends RequestInit {
  requireAuth?: boolean;
  _retried?: boolean;
  _silentError?: boolean;
}

async function getAuthToken(): Promise<string | null> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

async function refreshAndGetToken(): Promise<string | null> {
  const {
    data: { session },
    error,
  } = await supabase.auth.refreshSession();
  if (error || !session) {
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

function handleErrorResponse(status: number, errorMessage: string, silent?: boolean, retryAfter?: number): void {
  if (silent) return;

  switch (status) {
    case 401:
      toast.error('会话已过期，请重新登录', {
        id: 'auth-expired',
        action: {
          label: '去登录',
          onClick: () => {
            window.location.href = '/login';
          },
        },
      });
      break;
    case 403:
      toast.error('没有权限执行此操作', { id: 'no-permission' });
      break;
    case 422:
      toast.error(errorMessage || '请求参数有误');
      break;
    case 429: {
      const seconds = retryAfter || 60;
      toast.error(`请求频率超限，请 ${seconds} 秒后重试`, {
        id: 'rate-limit',
        duration: Math.min(seconds * 1000, 30000),
      });
      break;
    }
    case 500:
    case 502:
    case 503:
    case 504:
      toast.error('服务器错误，请稍后重试', { id: 'server-error' });
      break;
    default:
      if (status >= 400) {
        toast.error(errorMessage || `请求失败 (${status})`);
      }
      break;
  }
}

function handleNetworkError(error: Error, silent?: boolean): void {
  if (silent) return;

  const message = error.message || '';
  if (message.includes('Failed to fetch') || message.includes('NetworkError') || message.includes('network')) {
    toast.error('网络不可用，请检查网络连接', { id: 'network-error' });
  } else if (message.includes('AbortError') || error.name === 'AbortError') {
    return;
  } else {
    toast.error(message || '请求失败，请重试');
  }
}

async function parseErrorMessage(response: Response): Promise<string> {
  let errorMessage = `API Request Failed (${response.status})`;
  try {
    const errorData = await response.json();
    if (errorData.error?.message) {
      errorMessage = errorData.error.message;
    } else if (typeof errorData.detail === 'string') {
      errorMessage = errorData.detail;
    } else if (Array.isArray(errorData.detail)) {
      errorMessage = errorData.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(', ');
    }
  } catch {
    const text = await response.text().catch(() => response.statusText);
    errorMessage += `: ${text.slice(0, 100)}`;
  }
  return errorMessage;
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
      if (token) headers.Authorization = `Bearer ${token}`;
    }

    let response: Response;
    try {
      response = await fetch(fullUrl, { ...options, headers });
    } catch (networkError) {
      handleNetworkError(networkError as Error, silent);
      throw networkError;
    }

    if (response.status === 401 && !options._retried && options.requireAuth !== false) {
      const newToken = await refreshAndGetToken();
      if (newToken) {
        return this.fetch(endpoint, {
          ...options,
          _retried: true,
          headers: { ...(options.headers as Record<string, string>), Authorization: `Bearer ${newToken}` },
        });
      }
      handleErrorResponse(401, '会话已过期，请重新登录', silent);
      throw new Error('会话已过期，请重新登录');
    }

    if (!response.ok) {
      const errorMessage = await parseErrorMessage(response);
      const retryAfter = parseInt(response.headers.get('Retry-After') || '0', 10) || undefined;
      handleErrorResponse(response.status, errorMessage, silent, retryAfter);
      throw new Error(errorMessage);
    }

    return response.json();
  },

  async get<T = unknown>(endpoint: string, options: RequestOptions = {}): Promise<{ data: T }> {
    const data = await this.fetch(endpoint, { ...options, method: 'GET' });
    return { data };
  },

  async post<T = unknown>(endpoint: string, body?: unknown, options: RequestOptions = {}): Promise<{ data: T }> {
    const data = await this.fetch(endpoint, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
    return { data };
  },

  async put<T = unknown>(endpoint: string, body?: unknown, options: RequestOptions = {}): Promise<{ data: T }> {
    const data = await this.fetch(endpoint, {
      ...options,
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
    return { data };
  },

  async delete<T = unknown>(endpoint: string, options: RequestOptions = {}): Promise<{ data: T }> {
    const data = await this.fetch(endpoint, { ...options, method: 'DELETE' });
    return { data };
  },

  async processApproval(data: { requester_id: string; type: string; amount: number; details: string }) {
    return this.fetch('api/approval/process', {
      method: 'POST',
      body: JSON.stringify(data),
    }) as Promise<{ decision: string; reason: string }>;
  },

  async chat(messages: { role: string; content: string; [key: string]: unknown }[], model = 'gpt-4o') {
    return this.fetch('api/chat', {
      method: 'POST',
      body: JSON.stringify({ messages, model }),
    });
  },

  async uploadAudio(audioBlob: Blob, mimeType: string): Promise<{ data: { text: string; empty?: boolean } }> {
    const fullUrl = buildUrl('api/audio/transcribe');
    const ext = mimeType.includes('wav') ? '.wav' : mimeType.includes('mp4') ? '.m4a' : mimeType.includes('mp3') ? '.mp3' : '.webm';
    const formData = new FormData();
    formData.append('file', audioBlob, `recording${ext}`);

    const headers: Record<string, string> = { 'X-Trace-ID': getTraceId() };
    const token = await getAuthToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    let response: Response;
    try {
      response = await fetch(fullUrl, { method: 'POST', headers, body: formData });
    } catch (networkError) {
      handleNetworkError(networkError as Error);
      throw networkError;
    }

    if (!response.ok) {
      const errorMessage = await parseErrorMessage(response);
      handleErrorResponse(response.status, errorMessage);
      throw new Error(errorMessage || `语音识别失败 (${response.status})`);
    }

    return response.json();
  },
};

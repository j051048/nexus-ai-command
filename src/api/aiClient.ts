import type { AxiosError, AxiosRequestConfig, Method } from 'axios';
import { toast } from 'sonner';

import { supabase } from '@/integrations/supabase/client';
import { getApiBaseUrl } from '@/lib/apiConfig';
import { httpClient } from '@/lib/httpClient';

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

function buildUrl(endpoint: string): string {
  let url = getApiBaseUrl();
  if (!url.startsWith('http')) {
    url = url.includes('localhost') ? `http://${url}` : `https://${url}`;
  }
  const cleanBase = url.replace(/\/$/, '');
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  return `${cleanBase}/${cleanEndpoint}`;
}

function normalizeApiErrorMessage(status?: number, message?: string): string {
  const trimmed = message?.trim() || '';
  const normalized = trimmed.toLowerCase();
  if (
    status === 404 &&
    (!trimmed ||
      normalized === 'not found' ||
      normalized === '404' ||
      normalized.includes('not found') ||
      normalized.startsWith('api request failed (404)'))
  ) {
    return '当前功能暂不可用，请稍后重试';
  }
  if (trimmed) return trimmed;
  return status ? `请求失败 (${status})` : '请求失败，请重试';
}

function handleErrorResponse(
  status: number,
  errorMessage: string,
  silent?: boolean,
  retryAfter?: number
): void {
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
    case 404:
      toast.error(normalizeApiErrorMessage(status, errorMessage), { id: 'api-not-found' });
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
  if (silent || error.name === 'AbortError') return;

  const message = error.message || '';
  if (
    message.includes('Failed to fetch') ||
    message.includes('NetworkError') ||
    message.includes('network')
  ) {
    toast.error('网络不可用，请检查网络连接', { id: 'network-error' });
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
      errorMessage = errorData.detail
        .map((item: { msg?: string }) => item.msg)
        .filter(Boolean)
        .join(', ');
    }
  } catch {
    const text = await response.text().catch(() => response.statusText);
    errorMessage += `: ${text.slice(0, 100)}`;
  }
  return normalizeApiErrorMessage(response.status, errorMessage);
}

function parseAxiosErrorMessage(error: AxiosError<unknown>): string {
  const status = error.response?.status;
  const data = error.response?.data as
    | {
        error?: { message?: string };
        detail?: string | Array<{ msg?: string }>;
        message?: string;
      }
    | undefined;

  if (data?.error?.message) return normalizeApiErrorMessage(status, data.error.message);
  if (typeof data?.detail === 'string') return normalizeApiErrorMessage(status, data.detail);
  if (Array.isArray(data?.detail)) {
    const detail = data.detail
      .map((item) => item.msg)
      .filter(Boolean)
      .join(', ');
    if (detail) return normalizeApiErrorMessage(status, detail);
  }
  if (data?.message) return normalizeApiErrorMessage(status, data.message);
  return normalizeApiErrorMessage(
    status,
    status ? `API Request Failed (${status})` : error.message || 'API Request Failed'
  );
}

function normalizeJsonBody(
  body: BodyInit | null | undefined,
  contentType: string | undefined
): unknown {
  if (typeof body === 'string' && contentType?.includes('application/json')) {
    try {
      return JSON.parse(body);
    } catch {
      return body;
    }
  }
  return body;
}

export const aiClient = {
  async fetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const silent = options._silentError;
    const method = String(options.method ?? 'GET').toUpperCase();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Trace-ID': getTraceId(),
      ...(options.headers as Record<string, string>),
    };

    if (options.requireAuth === false) {
      headers['X-Skip-Optional-Auth'] = '1';
    }

    try {
      const requestConfig: AxiosRequestConfig = {
        url: endpoint,
        method: method as Method,
        headers,
        data: normalizeJsonBody(options.body, headers['Content-Type']),
        signal: options.signal,
        silentError: silent,
      };
      const response = await httpClient.request<T>(requestConfig);
      return response.data;
    } catch (requestError) {
      const maybeAxios = requestError as AxiosError<unknown>;
      if (maybeAxios.response) {
        const errorMessage = parseAxiosErrorMessage(maybeAxios);
        const retryAfterHeader = maybeAxios.response.headers?.['retry-after'];
        const retryAfter = parseInt(String(retryAfterHeader || '0'), 10) || undefined;
        // Read views own their loading/error state. A missing optional GET endpoint can
        // occur briefly during rolling deployments and should not interrupt every page.
        const suppressReadNotFound = method === 'GET' && maybeAxios.response.status === 404;
        if (suppressReadNotFound && !silent && import.meta.env.DEV) {
          console.warn('[aiClient] Optional read endpoint unavailable', {
            endpoint,
            status: maybeAxios.response.status,
          });
        }
        handleErrorResponse(
          maybeAxios.response.status,
          errorMessage,
          silent || suppressReadNotFound,
          retryAfter
        );
        throw new Error(errorMessage);
      }
      handleNetworkError(requestError as Error, silent);
      throw requestError;
    }
  },

  async stream(endpoint: string, options: RequestOptions = {}): Promise<Response> {
    const { requireAuth, _retried, _silentError, ...requestInit } = options;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Trace-ID': getTraceId(),
      ...(options.headers as Record<string, string>),
    };
    if (requireAuth !== false) {
      const token = await getAuthToken();
      if (!token) throw new Error('请先登录后再使用 AI 助手');
      headers.Authorization = `Bearer ${token}`;
    }
    try {
      return await fetch(buildUrl(endpoint), { ...requestInit, headers });
    } catch (networkError) {
      handleNetworkError(networkError as Error, _silentError);
      throw networkError;
    }
  },

  async get<T = unknown>(endpoint: string, options: RequestOptions = {}): Promise<{ data: T }> {
    const data = await this.fetch(endpoint, {
      ...options,
      method: 'GET',
      _silentError: options._silentError ?? true,
    });
    return { data };
  },

  async post<T = unknown>(
    endpoint: string,
    body?: unknown,
    options: RequestOptions = {}
  ): Promise<{ data: T }> {
    const data = await this.fetch(endpoint, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
    return { data };
  },

  async put<T = unknown>(
    endpoint: string,
    body?: unknown,
    options: RequestOptions = {}
  ): Promise<{ data: T }> {
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

  async processApproval(data: {
    requester_id: string;
    type: string;
    amount: number;
    details: string;
  }) {
    return this.fetch('api/approval/process', {
      method: 'POST',
      body: JSON.stringify(data),
    }) as Promise<{ decision: string; reason: string }>;
  },

  async chat(
    messages: { role: string; content: string; [key: string]: unknown }[],
    model = 'deepseek-v4-flash'
  ) {
    return this.fetch('api/chat', {
      method: 'POST',
      body: JSON.stringify({ messages, model }),
    });
  },

  async uploadAudio(
    audioBlob: Blob,
    mimeType: string
  ): Promise<{ data: { text: string; empty?: boolean } }> {
    const fullUrl = buildUrl('api/audio/transcribe');
    const ext = mimeType.includes('wav')
      ? '.wav'
      : mimeType.includes('mp4')
        ? '.m4a'
        : mimeType.includes('mp3')
          ? '.mp3'
          : '.webm';
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

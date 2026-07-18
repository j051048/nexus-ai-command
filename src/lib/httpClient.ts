import axios, { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import { toast } from 'sonner';

import { supabase } from '@/integrations/supabase/client';

import { getApiBaseUrl } from './apiConfig';

const httpClient: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 60000,
  withCredentials: true,
});

type SilentRequestConfig = AxiosRequestConfig & { silentError?: boolean };
type SilentInternalRequestConfig = InternalAxiosRequestConfig & { silentError?: boolean };

httpClient.interceptors.request.use(
  async (config) => {
    const requestConfig = config as SilentInternalRequestConfig;
    const legacySilentHeader = requestConfig.headers['X-Silent-Error'];
    if (String(legacySilentHeader ?? '') === '1') {
      requestConfig.silentError = true;
      delete requestConfig.headers['X-Silent-Error'];
    }

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session?.access_token) {
        config.headers.Authorization = `Bearer ${session.access_token}`;
      }
    } catch (error) {
      console.error('Failed to get session:', error);
    }

    const orgId = localStorage.getItem('current_org_id');
    if (orgId) {
      config.headers['X-Org-ID'] = orgId;
    }

    const method = config.method?.toLowerCase() || '';
    if (['post', 'put', 'delete', 'patch'].includes(method)) {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken;
      }
    }

    if (['post', 'put'].includes(method) && !config.headers['X-Idempotency-Key']) {
      config.headers['X-Idempotency-Key'] =
        `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
    }

    config.headers['X-Requested-With'] = 'XMLHttpRequest';
    return config;
  },
  (error) => Promise.reject(error)
);

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const silent = Boolean((error.config as SilentRequestConfig | undefined)?.silentError);

    if (silent) {
      return Promise.reject(error);
    }

    if (status === 401 && window.location.pathname !== '/login') {
      toast.error('登录已过期，请重新登录', { id: 'auth-expired' });
      localStorage.removeItem('supabase.auth.token');
      Object.keys(localStorage).forEach((key) => {
        if (key.startsWith('sb-') && key.endsWith('-auth-token')) {
          localStorage.removeItem(key);
        }
      });
      window.location.href = '/login';
    }

    if (status === 403) {
      toast.error('权限不足或请求被拒绝', { id: 'request-forbidden' });
    }
    if (status === 429) {
      toast.error('请求过于频繁，请稍后再试', { id: 'request-rate-limited' });
    }
    if (status === 500) {
      toast.error('服务器错误，请稍后重试', { id: 'server-error' });
    }

    return Promise.reject(error);
  }
);

export { httpClient };

/**
 * 统一 HTTP 客户端
 * 解决 401、CSRF、租户隔离等问题
 */
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import { getApiBaseUrl } from './apiConfig';
import { toast } from 'sonner';

// 创建 axios 实例
const httpClient: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 60000,
  withCredentials: true, // 携带 Cookie
});

// 请求拦截器
httpClient.interceptors.request.use(
  (config) => {
    // 1. 注入 Token
    const token = localStorage.getItem('supabase.auth.token') ||
                  sessionStorage.getItem('supabase.auth.token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // 2. 注入租户 ID
    const orgId = localStorage.getItem('current_org_id');
    if (orgId) {
      config.headers['X-Org-ID'] = orgId;
    }

    // 3. POST/PUT/DELETE 请求注入 CSRF Token
    if (['post', 'put', 'delete', 'patch'].includes(config.method?.toLowerCase() || '')) {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken;
      }
    }

    // 4. 幂等性 Key（防重放）
    if (['post', 'put'].includes(config.method?.toLowerCase() || '')) {
      config.headers['X-Idempotency-Key'] = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }

    // 5. 标识前端请求
    config.headers['X-Requested-With'] = 'XMLHttpRequest';

    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    // 401: Token 过期或无效
    if (status === 401) {
      toast.error('登录已过期，请重新登录');
      localStorage.removeItem('supabase.auth.token');
      window.location.href = '/login';
    }

    // 403: CSRF 或权限不足
    if (status === 403) {
      toast.error('权限不足或请求被拒绝');
    }

    // 429: 限流
    if (status === 429) {
      toast.error('请求过于频繁，请稍后再试');
    }

    // 500: 服务器错误
    if (status === 500) {
      toast.error('服务器错误，请稍后重试');
    }

    return Promise.reject(error);
  }
);

export default httpClient;

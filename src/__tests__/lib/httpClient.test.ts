import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import httpClient from '../../lib/httpClient';
import { AxiosRequestConfig } from 'axios';
import { toast } from 'sonner';

// Mock 外部依赖
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));
vi.mock('../../lib/apiConfig', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

describe('httpClient interceptors', () => {
  let requestConfig: AxiosRequestConfig;
  let originalLocation: Location;

  beforeEach(() => {
    vi.clearAllMocks();
    requestConfig = {
      headers: {},
      method: 'get'
    };
    
    // 模拟 localStorage 和 sessionStorage
    const mockGetItem = vi.fn((key) => {
      if (key === 'supabase.auth.token') return 'mock-token-123';
      if (key === 'current_org_id') return 'mock-org-456';
      return null;
    });
    vi.spyOn(window.localStorage, 'getItem').mockImplementation(mockGetItem);
    vi.spyOn(window.sessionStorage, 'getItem').mockImplementation(() => null);
    vi.spyOn(window.localStorage, 'removeItem').mockImplementation(() => {});

    // 劫持 window.location
    originalLocation = window.location;
    // @ts-expect-error mock window.location
    delete window.location;
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
      configurable: true,
    });

    // 清空 body 以准备 meta tag 测试
    document.head.innerHTML = '';
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
    vi.restoreAllMocks();
  });

  describe('Request Interceptor', () => {
    it('应该正确注入 Token、Org-ID 和全局标记', async () => {
      // @ts-expect-error access private handlers for test
      const handler = httpClient.interceptors.request.handlers[0];
      // @ts-expect-error mock request config type mismatch
      const config = await handler.fulfilled(requestConfig);

      // 断言
      expect(config.headers.Authorization).toBe('Bearer mock-token-123');
      expect(config.headers['X-Org-ID']).toBe('mock-org-456');
      expect(config.headers['X-Requested-With']).toBe('XMLHttpRequest');
    });

    it('对于 POST 请求，应该注入 CSRF 和 幂等性 Key', async () => {
      // 模拟 meta 标签存在
      document.head.innerHTML = '<meta name="csrf-token" content="mock-csrf-token-abc" />';
      requestConfig.method = 'post';

      // @ts-expect-error access private handlers for test
      const handler = httpClient.interceptors.request.handlers[0];
      // @ts-expect-error mock request config type mismatch
      const config = await handler.fulfilled(requestConfig);

      expect(config.headers['X-CSRF-Token']).toBe('mock-csrf-token-abc');
      expect(config.headers['X-Idempotency-Key']).toBeDefined(); // 需要有一串时间戳随机值
      expect(config.headers['X-Idempotency-Key']).toMatch(/^\d+-/);
    });

    it('对于 GET 请求，不应该注入 CSRF 和 幂等性 Key', async () => {
      document.head.innerHTML = '<meta name="csrf-token" content="mock-csrf-token-abc" />';
      requestConfig.method = 'get';

      // @ts-expect-error access private handlers for test
      const handler = httpClient.interceptors.request.handlers[0];
      // @ts-expect-error mock request config type mismatch
      const config = await handler.fulfilled(requestConfig);

      expect(config.headers['X-CSRF-Token']).toBeUndefined();
      expect(config.headers['X-Idempotency-Key']).toBeUndefined();
    });
  });

  describe('Response Interceptor Error Handling', () => {
    // 提取响应拦截器错误处理器
    const runErrorInterceptor = async (status: number) => {
      // @ts-expect-error access private handlers for test
      const handler = httpClient.interceptors.response.handlers[0];
      try {
        if (handler.rejected) {
          await handler.rejected({ response: { status } });
        }
      } catch (e) {
        // expected to reject
      }
    };

    it('遇到 401 应该弹出错误、清除缓存并跳转登录', async () => {
      await runErrorInterceptor(401);

      expect(toast.error).toHaveBeenCalledWith('登录已过期，请重新登录');
      expect(localStorage.removeItem).toHaveBeenCalledWith('supabase.auth.token');
      expect(window.location.href).toBe('/login');
    });

    it('遇到 403 应该弹出权限不足错误', async () => {
      await runErrorInterceptor(403);
      expect(toast.error).toHaveBeenCalledWith('权限不足或请求被拒绝');
    });

    it('遇到 429 应该弹流控提示', async () => {
      await runErrorInterceptor(429);
      expect(toast.error).toHaveBeenCalledWith('请求过于频繁，请稍后再试');
    });

    it('遇到 500 应该弹出服务器内部错误', async () => {
      await runErrorInterceptor(500);
      expect(toast.error).toHaveBeenCalledWith('服务器错误，请稍后重试');
    });
  });
});

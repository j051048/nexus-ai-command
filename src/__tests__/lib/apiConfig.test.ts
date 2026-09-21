/**
 * getApiBaseUrl 单元测试
 *
 * 覆盖：环境变量配置、协议补全、尾斜杠清理、localhost 回退、生产环境 origin 回退
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('getApiBaseUrl', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true });
  });

  it('使用 VITE_API_BASE_URL 环境变量（带 https）', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com/');
    const { getApiBaseUrl } = await import('@/lib/apiConfig');
    expect(getApiBaseUrl()).toBe('https://api.example.com');
  });

  it('自动补全 https 协议', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'api.example.com');
    const { getApiBaseUrl } = await import('@/lib/apiConfig');
    expect(getApiBaseUrl()).toBe('https://api.example.com');
  });

  it('保留 http 协议不覆盖', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    const { getApiBaseUrl } = await import('@/lib/apiConfig');
    expect(getApiBaseUrl()).toBe('http://localhost:8000');
  });

  it('去除尾部斜杠', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com/');
    const { getApiBaseUrl } = await import('@/lib/apiConfig');
    expect(getApiBaseUrl()).not.toMatch(/\/$/);
  });

  it('未配置时 localhost 回退到 http://localhost:8000', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '');
    Object.defineProperty(window, 'location', {
      value: { hostname: 'localhost', origin: 'http://localhost:5173' },
      writable: true,
    });
    const { getApiBaseUrl } = await import('@/lib/apiConfig');
    expect(getApiBaseUrl()).toBe('http://localhost:8000');
  });

  it('未配置时生产环境回退到 window.location.origin', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '');
    Object.defineProperty(window, 'location', {
      value: { hostname: 'app.nexus.com', origin: 'https://app.nexus.com' },
      writable: true,
    });
    const { getApiBaseUrl } = await import('@/lib/apiConfig');
    expect(getApiBaseUrl()).toBe('https://app.nexus.com');
  });

  it('preview 环境未配置 VITE_API_BASE_URL 时显式失败，避免写到生产', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '');
    vi.stubEnv('VITE_APP_ENV', 'preview');
    Object.defineProperty(window, 'location', {
      value: { hostname: 'pr-42.nexus.preview', origin: 'https://pr-42.nexus.preview' },
      writable: true,
    });
    const { getApiBaseUrl } = await import('@/lib/apiConfig');
    expect(() => getApiBaseUrl()).toThrow(/VITE_API_BASE_URL is required/);
  });

  it('staging 环境未配置 VITE_API_BASE_URL 时显式失败', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '');
    vi.stubEnv('VITE_APP_ENV', 'staging');
    Object.defineProperty(window, 'location', {
      value: { hostname: 'staging.nexus.com', origin: 'https://staging.nexus.com' },
      writable: true,
    });
    const { getApiBaseUrl } = await import('@/lib/apiConfig');
    expect(() => getApiBaseUrl()).toThrow(/VITE_API_BASE_URL is required/);
  });

  it('preview 环境配置了 VITE_API_BASE_URL 时使用配置值', async () => {
    vi.stubEnv('VITE_APP_ENV', 'preview');
    vi.stubEnv('VITE_API_BASE_URL', 'https://staging-api.nexus.com');
    const { getApiBaseUrl } = await import('@/lib/apiConfig');
    expect(getApiBaseUrl()).toBe('https://staging-api.nexus.com');
  });
});

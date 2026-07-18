import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  request: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('@/lib/httpClient', () => ({
  httpClient: { request: mocks.request },
}));

vi.mock('@/integrations/supabase/client', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  },
}));

vi.mock('@/lib/apiConfig', () => ({
  getApiBaseUrl: () => 'https://api.test.com',
}));

vi.mock('sonner', () => ({
  toast: { error: mocks.toastError },
}));

import { aiClient } from '@/api/aiClient';

function missingEndpointError() {
  return {
    message: 'Request failed with status code 404',
    response: {
      status: 404,
      data: { detail: 'Not Found' },
      headers: {},
    },
  };
}

describe('aiClient error presentation policy', () => {
  beforeEach(() => {
    mocks.request.mockReset();
    mocks.toastError.mockReset();
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  it('does not interrupt the workspace for a missing read endpoint', async () => {
    mocks.request.mockRejectedValueOnce(missingEndpointError());

    await expect(aiClient.fetch('/api/optional-read')).rejects.toThrow(
      '当前功能暂不可用，请稍后重试'
    );

    expect(mocks.toastError).not.toHaveBeenCalled();
  });

  it('keeps a visible error for a missing write endpoint', async () => {
    mocks.request.mockRejectedValueOnce(missingEndpointError());

    await expect(
      aiClient.fetch('/api/required-action', { method: 'POST' })
    ).rejects.toThrow('当前功能暂不可用，请稍后重试');

    expect(mocks.toastError).toHaveBeenCalledWith(
      '当前功能暂不可用，请稍后重试',
      { id: 'api-not-found' }
    );
  });
});

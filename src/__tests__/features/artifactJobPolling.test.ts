import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/httpClient', () => ({ httpClient: { get: vi.fn(), post: vi.fn() } }));
vi.mock('@/features/deliverables/exportContent', () => ({ downloadBlob: vi.fn() }));

import { httpClient } from '@/lib/httpClient';
import { waitForArtifactJob, type ArtifactGenerationJob } from '@/features/deliverables/artifactApi';

const queued: ArtifactGenerationJob = { id: 'job-1', status: 'queued', stage: 'queued', progress: 0, progress_details: {}, attempt: 1, max_attempts: 3 };

afterEach(() => { vi.useRealTimers(); vi.resetAllMocks(); });

describe('durable artifact polling', () => {
  it('reconnects to the same job without resubmitting generation', async () => {
    vi.useFakeTimers();
    vi.mocked(httpClient.get).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ data: { data: { ...queued, status: 'completed', result: { id: 'artifact-1' } } } });
    const pending = waitForArtifactJob(queued);
    await vi.runAllTimersAsync();
    expect(await pending).toMatchObject({ id: 'artifact-1' });
    expect(httpClient.post).not.toHaveBeenCalled();
    expect(httpClient.get).toHaveBeenCalledTimes(2);
  });

  it('does not retry an authorization failure', async () => {
    vi.useFakeTimers();
    vi.mocked(httpClient.get).mockRejectedValue({ response: { status: 403 } });
    const assertion = expect(waitForArtifactJob(queued)).rejects.toMatchObject({ response: { status: 403 } });
    await vi.runAllTimersAsync();
    await assertion;
    expect(httpClient.get).toHaveBeenCalledTimes(1);
  });

  it('bounds reconnect attempts and keeps the task recoverable', async () => {
    vi.useFakeTimers();
    vi.mocked(httpClient.get).mockRejectedValue(new Error('offline'));
    const assertion = expect(waitForArtifactJob(queued)).rejects.toThrow('成果中心');
    await vi.runAllTimersAsync();
    await assertion;
    expect(httpClient.get).toHaveBeenCalledTimes(5);
  });
});

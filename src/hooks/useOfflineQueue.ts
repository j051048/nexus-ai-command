import { useState, useEffect, useCallback, useRef } from 'react';
import {
  offlineQueue,
  OfflineQueueIdentity,
  QueuedOperation,
  ReplayResult,
} from '@/services/offlineQueue';

/**
 * 离线操作队列 Hook
 *
 * 提供:
 * - isOnline: 当前网络状态
 * - count: 待同步操作数量
 * - enqueue: 入队操作
 * - replay: 手动重放队列
 * - clear: 清空队列
 *
 * 网络恢复时自动重放队列。
 */
export function useOfflineQueue(
  identity?: OfflineQueueIdentity,
  getReplayHeaders?: () => Record<string, string> | Promise<Record<string, string>>,
) {
  const [count, setCount] = useState(0);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isReplaying, setIsReplaying] = useState(false);
  const replayingRef = useRef(false);

  // 更新队列计数
  const refreshCount = useCallback(async () => {
    try {
      const c = identity ? await offlineQueue.getCount(identity) : 0;
      setCount(c);
    } catch {
      // IndexedDB may not be available
    }
  }, [identity]);

  // 初始化队列
  useEffect(() => {
    offlineQueue.init().then(() => refreshCount());
  }, [refreshCount]);

  // 监听在线/离线事件
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      // 自动重放队列
      if (identity && !replayingRef.current) {
        replayingRef.current = true;
        setIsReplaying(true);
        offlineQueue
          .replay({ identity, getHeaders: getReplayHeaders })
          .then(() => refreshCount())
          .finally(() => {
            replayingRef.current = false;
            setIsReplaying(false);
          });
      }
    };

    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [getReplayHeaders, identity, refreshCount]);

  // 入队操作
  const enqueue = useCallback(
    async (
      operation: Omit<
        QueuedOperation,
        | 'id'
        | 'timestamp'
        | 'retries'
        | 'organizationId'
        | 'userId'
        | 'sessionId'
        | 'identityKey'
        | 'idempotencyKey'
        | 'state'
        | 'lastError'
      > & { idempotencyKey?: string },
    ) => {
      if (!identity) throw new Error('Offline queue identity is required');
      const id = await offlineQueue.enqueue({ ...operation, identity });
      await refreshCount();
      return id;
    },
    [identity, refreshCount]
  );

  // 手动重放
  const replay = useCallback(async () => {
    const empty: ReplayResult = { success: 0, failed: 0, blocked: 0, conflicts: 0 };
    if (replayingRef.current || !identity) return empty;
    replayingRef.current = true;
    setIsReplaying(true);
    try {
      const result = await offlineQueue.replay({ identity, getHeaders: getReplayHeaders });
      await refreshCount();
      return result;
    } finally {
      replayingRef.current = false;
      setIsReplaying(false);
    }
  }, [getReplayHeaders, identity, refreshCount]);

  // 清空队列
  const clear = useCallback(async () => {
    if (identity) await offlineQueue.clear(identity);
    await refreshCount();
  }, [identity, refreshCount]);

  return {
    isOnline,
    isReplaying,
    count,
    enqueue,
    replay,
    clear,
    refreshCount,
  };
}

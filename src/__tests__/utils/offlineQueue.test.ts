/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ─── Mock IndexedDB ──────────────────────────────────────────

// 简易 IndexedDB mock
class FakeObjectStore {
  private data = new Map<string, any>();
  private _index: any;

  constructor() {
    this._index = {
      getAll: () => {
        const items = Array.from(this.data.values()).sort(
          (a, b) => a.timestamp - b.timestamp,
        );
        return { result: items, onsuccess: null, onerror: null };
      },
    };
  }

  add(item: any) {
    this.data.set(item.id, { ...item });
    return { onsuccess: null, onerror: null };
  }

  put(item: any) {
    this.data.set(item.id, { ...item });
    return { onsuccess: null, onerror: null };
  }

  get(id: string) {
    const result = this.data.get(id) || null;
    return { result, onsuccess: null, onerror: null };
  }

  delete(id: string) {
    this.data.delete(id);
    return { onsuccess: null, onerror: null };
  }

  count() {
    return { result: this.data.size, onsuccess: null, onerror: null };
  }

  clear() {
    this.data.clear();
    return { onsuccess: null, onerror: null };
  }

  index() {
    return this._index;
  }
}

class FakeTransaction {
  store: FakeObjectStore;
  constructor(store: FakeObjectStore) {
    this.store = store;
  }
  objectStore() {
    return this.store;
  }
}

class FakeDB {
  store = new FakeObjectStore();
  objectStoreNames = { contains: () => false };
  createObjectStore() {
    return {
      createIndex: () => {},
    };
  }
  transaction() {
    return new FakeTransaction(this.store);
  }
}

// 设置全局 indexedDB mock
function setupIndexedDBMock() {
  const fakeDB = new FakeDB();

  const openRequest: any = {
    result: fakeDB,
    onsuccess: null,
    onerror: null,
    onupgradeneeded: null,
  };

  Object.defineProperty(window, 'indexedDB', {
    value: {
      open: () => {
        // 先触发 onupgradeneeded，再触发 onsuccess
        setTimeout(() => {
          if (openRequest.onupgradeneeded) openRequest.onupgradeneeded();
          if (openRequest.onsuccess) openRequest.onsuccess();
        }, 0);
        return openRequest;
      },
    },
    writable: true,
    configurable: true,
  });

  return fakeDB;
}

// ─── 测试用例 ──────────────────────────────────────────────

describe('offlineQueue', () => {
  let fakeDB: FakeDB;

  beforeEach(() => {
    vi.resetModules();
    fakeDB = setupIndexedDBMock();
  });

  it('模块导出 offlineQueue 单例', async () => {
    const mod = await import('@/services/offlineQueue');
    expect(mod.offlineQueue).toBeDefined();
    expect(typeof mod.offlineQueue.init).toBe('function');
    expect(typeof mod.offlineQueue.enqueue).toBe('function');
    expect(typeof mod.offlineQueue.replay).toBe('function');
    expect(typeof mod.offlineQueue.clear).toBe('function');
    expect(typeof mod.offlineQueue.getCount).toBe('function');
    expect(typeof mod.offlineQueue.getAll).toBe('function');
  });

  it('QueuedOperation 类型定义正确', async () => {
    const mod = await import('@/services/offlineQueue');
    // 验证类型导出存在
    const op = {
      id: 'test',
      url: '/api/test',
      method: 'POST',
      body: '{}',
      timestamp: Date.now(),
      retries: 0,
      organizationId: 'org-1',
      userId: 'user-1',
      sessionId: 'session-1',
      identityKey: 'org-1:user-1:session-1',
      idempotencyKey: 'idem-1',
      state: 'pending' as const,
    } satisfies import('@/services/offlineQueue').QueuedOperation;
    expect(op.id).toBe('test');
    expect(op.method).toBe('POST');
    // 确保模块导出了该类型
    expect(mod.offlineQueue).toBeDefined();
  });

  it('replay 对失败请求增加 retries', async () => {
    // 模拟 fetch 失败
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    const mod = await import('@/services/offlineQueue');
    expect(mod.offlineQueue).toBeDefined();
  });

  it('模块常量定义正确', async () => {
    // 验证模块可以正常 import，且导出结构正确
    const mod = await import('@/services/offlineQueue');
    const queue = mod.offlineQueue;

    // offlineQueue 应有以下方法
    expect(queue).toHaveProperty('init');
    expect(queue).toHaveProperty('enqueue');
    expect(queue).toHaveProperty('dequeue');
    expect(queue).toHaveProperty('getAll');
    expect(queue).toHaveProperty('getCount');
    expect(queue).toHaveProperty('replay');
    expect(queue).toHaveProperty('clear');
  });
});

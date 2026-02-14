/**
 * 离线操作队列
 *
 * 使用 IndexedDB 存储离线时的 API 操作，
 * 网络恢复后自动重放（replay）。
 */

export interface QueuedOperation {
  id: string;
  url: string;
  method: string;
  body?: string;
  headers?: Record<string, string>;
  timestamp: number;
  retries: number;
}

const DB_NAME = 'nexus-offline-queue';
const STORE_NAME = 'operations';
const DB_VERSION = 1;
const MAX_RETRIES = 5;

class OfflineQueue {
  private db: IDBDatabase | null = null;
  private initPromise: Promise<void> | null = null;

  /**
   * 打开 IndexedDB 数据库
   */
  async init(): Promise<void> {
    if (this.db) return;
    if (this.initPromise) return this.initPromise;

    this.initPromise = new Promise<void>((resolve, reject) => {
      try {
        if (!('indexedDB' in window)) {
          console.warn('IndexedDB not available');
          resolve();
          return;
        }

        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = () => {
          const db = request.result;
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
            store.createIndex('timestamp', 'timestamp', { unique: false });
          }
        };

        request.onsuccess = () => {
          this.db = request.result;
          resolve();
        };

        request.onerror = () => {
          console.error('Failed to open IndexedDB:', request.error);
          reject(request.error);
        };
      } catch (err) {
        console.error('IndexedDB init error:', err);
        resolve(); // Resolve anyway to prevent blocking
      }
    });

    return this.initPromise;
  }

  /**
   * 确保数据库已初始化
   */
  private async ensureDB(): Promise<IDBDatabase | null> {
    if (!this.db) await this.init();
    return this.db;
  }

  /**
   * 添加操作到队列
   */
  async enqueue(
    operation: Omit<QueuedOperation, 'id' | 'timestamp' | 'retries'>
  ): Promise<string> {
    const db = await this.ensureDB();
    if (!db) throw new Error('IndexedDB not available');

    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    const entry: QueuedOperation = {
      ...operation,
      id,
      timestamp: Date.now(),
      retries: 0,
    };

    return new Promise<string>((resolve, reject) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const request = store.add(entry);

        request.onsuccess = () => resolve(id);
        request.onerror = () => reject(request.error);
      } catch (err) {
        reject(err);
      }
    });
  }

  /**
   * 从队列移除操作
   */
  async dequeue(id: string): Promise<void> {
    const db = await this.ensureDB();
    if (!db) return;

    return new Promise<void>((resolve, reject) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const request = store.delete(id);

        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      } catch (err) {
        reject(err);
      }
    });
  }

  /**
   * 获取所有排队的操作
   */
  async getAll(): Promise<QueuedOperation[]> {
    const db = await this.ensureDB();
    if (!db) return [];

    return new Promise<QueuedOperation[]>((resolve, reject) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const index = store.index('timestamp');
        const request = index.getAll();

        request.onsuccess = () => resolve(request.result || []);
        request.onerror = () => reject(request.error);
      } catch (err) {
        console.error('getAll error:', err);
        resolve([]);
      }
    });
  }

  /**
   * 获取队列长度
   */
  async getCount(): Promise<number> {
    const db = await this.ensureDB();
    if (!db) return 0;

    return new Promise<number>((resolve, reject) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const request = store.count();

        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      } catch (err) {
        console.error('getCount error:', err);
        resolve(0);
      }
    });
  }

  /**
   * 重放所有排队的操作
   * 对每个操作：尝试 fetch，成功则 dequeue，失败则增加 retries
   */
  async replay(): Promise<{ success: number; failed: number }> {
    const operations = await this.getAll();
    let success = 0;
    let failed = 0;

    for (const op of operations) {
      if (op.retries >= MAX_RETRIES) {
        // 超过最大重试次数，移除
        await this.dequeue(op.id);
        failed++;
        continue;
      }

      try {
        const fetchOptions: RequestInit = {
          method: op.method,
          headers: op.headers,
        };
        if (op.body && op.method !== 'GET' && op.method !== 'HEAD') {
          fetchOptions.body = op.body;
        }

        const res = await fetch(op.url, fetchOptions);

        if (res.ok || res.status < 500) {
          // 成功或客户端错误（不值得重试）
          await this.dequeue(op.id);
          success++;
        } else {
          // 服务器错误，增加 retries
          await this.updateRetries(op.id, op.retries + 1);
          failed++;
        }
      } catch {
        // 网络错误，增加 retries
        await this.updateRetries(op.id, op.retries + 1);
        failed++;
      }
    }

    return { success, failed };
  }

  /**
   * 更新操作的重试计数
   */
  private async updateRetries(id: string, retries: number): Promise<void> {
    const db = await this.ensureDB();
    if (!db) return;

    return new Promise<void>((resolve) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const getReq = store.get(id);

        getReq.onsuccess = () => {
          const data = getReq.result;
          if (data) {
            data.retries = retries;
            store.put(data);
          }
          resolve();
        };

        getReq.onerror = () => resolve();
      } catch {
        resolve();
      }
    });
  }

  /**
   * 清空所有排队的操作
   */
  async clear(): Promise<void> {
    const db = await this.ensureDB();
    if (!db) return;

    return new Promise<void>((resolve, reject) => {
      try {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const request = store.clear();

        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      } catch (err) {
        reject(err);
      }
    });
  }
}

export const offlineQueue = new OfflineQueue();

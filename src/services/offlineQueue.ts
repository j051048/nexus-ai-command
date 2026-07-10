/**
 * Tenant-safe offline mutation queue.
 *
 * Authentication secrets are never persisted. Every queued operation is bound
 * to the user, organization and login session that created it, and replay only
 * targets same-origin /api endpoints with a stable idempotency key.
 */

export interface OfflineQueueIdentity {
  organizationId: string;
  userId: string;
  sessionId: string;
}

export type OfflineQueueState = 'pending' | 'blocked' | 'conflict' | 'dead_letter';

export interface QueuedOperation {
  id: string;
  url: string;
  method: string;
  body?: string;
  headers?: Record<string, string>;
  timestamp: number;
  retries: number;
  organizationId: string;
  userId: string;
  sessionId: string;
  identityKey: string;
  idempotencyKey: string;
  state: OfflineQueueState;
  lastError?: string;
}

export interface ReplayContext {
  identity: OfflineQueueIdentity;
  getHeaders?: () => Record<string, string> | Promise<Record<string, string>>;
}

export interface ReplayResult {
  success: number;
  failed: number;
  blocked: number;
  conflicts: number;
}

type NewQueuedOperation = Omit<
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
> & {
  identity: OfflineQueueIdentity;
  idempotencyKey?: string;
};

const DB_NAME = 'nexus-offline-queue';
const STORE_NAME = 'operations';
const DB_VERSION = 2;
const MAX_RETRIES = 5;
const SAFE_PERSISTED_HEADERS = new Set([
  'accept',
  'content-type',
  'if-match',
  'if-none-match',
]);

function identityKey(identity: OfflineQueueIdentity): string {
  return `${identity.organizationId}:${identity.userId}:${identity.sessionId}`;
}

function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

function sanitizePersistedHeaders(headers?: Record<string, string>): Record<string, string> {
  if (!headers) return {};
  return Object.fromEntries(
    Object.entries(headers).filter(([name]) => SAFE_PERSISTED_HEADERS.has(name.toLowerCase())),
  );
}

function validateOfflineUrl(rawUrl: string): string {
  const url = new URL(rawUrl, window.location.origin);
  if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/')) {
    throw new Error('Offline replay only supports same-origin /api endpoints');
  }
  return `${url.pathname}${url.search}`;
}

class OfflineQueue {
  private db: IDBDatabase | null = null;
  private initPromise: Promise<void> | null = null;

  async init(): Promise<void> {
    if (this.db) return;
    if (this.initPromise) return this.initPromise;

    this.initPromise = new Promise<void>((resolve, reject) => {
      try {
        if (!('indexedDB' in window)) {
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
        request.onerror = () => reject(request.error);
      } catch (error) {
        console.error('IndexedDB init error:', error);
        resolve();
      }
    });

    return this.initPromise;
  }

  private async ensureDB(): Promise<IDBDatabase | null> {
    if (!this.db) await this.init();
    return this.db;
  }

  async enqueue(operation: NewQueuedOperation): Promise<string> {
    const db = await this.ensureDB();
    if (!db) throw new Error('IndexedDB not available');

    const id = newId();
    const entry: QueuedOperation = {
      id,
      url: validateOfflineUrl(operation.url),
      method: operation.method.toUpperCase(),
      body: operation.body,
      headers: sanitizePersistedHeaders(operation.headers),
      timestamp: Date.now(),
      retries: 0,
      organizationId: operation.identity.organizationId,
      userId: operation.identity.userId,
      sessionId: operation.identity.sessionId,
      identityKey: identityKey(operation.identity),
      idempotencyKey: operation.idempotencyKey || newId(),
      state: 'pending',
    };

    return new Promise<string>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const request = tx.objectStore(STORE_NAME).add(entry);
      request.onsuccess = () => resolve(id);
      request.onerror = () => reject(request.error);
    });
  }

  async dequeue(id: string): Promise<void> {
    const db = await this.ensureDB();
    if (!db) return;
    return new Promise<void>((resolve, reject) => {
      const request = db.transaction(STORE_NAME, 'readwrite').objectStore(STORE_NAME).delete(id);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  async getAll(identity?: OfflineQueueIdentity): Promise<QueuedOperation[]> {
    const db = await this.ensureDB();
    if (!db) return [];
    return new Promise<QueuedOperation[]>((resolve, reject) => {
      const store = db.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME);
      const request = store.index('timestamp').getAll();
      request.onsuccess = () => {
        const rows = (request.result || []) as QueuedOperation[];
        const key = identity ? identityKey(identity) : null;
        resolve(key ? rows.filter((row) => row.identityKey === key) : rows);
      };
      request.onerror = () => reject(request.error);
    });
  }

  async getCount(identity?: OfflineQueueIdentity): Promise<number> {
    if (identity) return (await this.getAll(identity)).length;
    const db = await this.ensureDB();
    if (!db) return 0;
    return new Promise<number>((resolve, reject) => {
      const request = db.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME).count();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async replay(context: ReplayContext): Promise<ReplayResult> {
    const operations = await this.getAll(context.identity);
    const result: ReplayResult = { success: 0, failed: 0, blocked: 0, conflicts: 0 };
    const runtimeHeaders = context.getHeaders ? await context.getHeaders() : {};

    for (const operation of operations) {
      if (operation.state !== 'pending') continue;
      if (operation.retries >= MAX_RETRIES) {
        await this.update(operation.id, {
          state: 'dead_letter',
          lastError: `Maximum retry count (${MAX_RETRIES}) reached`,
        });
        result.failed++;
        continue;
      }

      try {
        const headers = {
          ...operation.headers,
          ...runtimeHeaders,
          'X-Idempotency-Key': operation.idempotencyKey,
        };
        const response = await fetch(validateOfflineUrl(operation.url), {
          method: operation.method,
          headers,
          body:
            operation.body && !['GET', 'HEAD'].includes(operation.method)
              ? operation.body
              : undefined,
          credentials: 'same-origin',
        });

        if (response.ok) {
          await this.dequeue(operation.id);
          result.success++;
        } else if ([401, 403].includes(response.status)) {
          await this.update(operation.id, {
            state: 'blocked',
            lastError: `Authorization rejected (${response.status})`,
          });
          result.blocked++;
        } else if ([409, 412, 422].includes(response.status)) {
          await this.update(operation.id, {
            state: 'conflict',
            lastError: `Server rejected stale or conflicting data (${response.status})`,
          });
          result.conflicts++;
        } else if (response.status === 429 || response.status >= 500) {
          await this.update(operation.id, {
            retries: operation.retries + 1,
            lastError: `Retryable server response (${response.status})`,
          });
          result.failed++;
        } else {
          await this.update(operation.id, {
            state: 'blocked',
            lastError: `Non-retryable client response (${response.status})`,
          });
          result.blocked++;
        }
      } catch (error) {
        await this.update(operation.id, {
          retries: operation.retries + 1,
          lastError: error instanceof Error ? error.message : 'Network error',
        });
        result.failed++;
      }
    }

    return result;
  }

  async updateRetries(id: string, retries: number): Promise<void> {
    await this.update(id, { retries });
  }

  private async update(id: string, patch: Partial<QueuedOperation>): Promise<void> {
    const db = await this.ensureDB();
    if (!db) return;
    return new Promise<void>((resolve) => {
      const store = db.transaction(STORE_NAME, 'readwrite').objectStore(STORE_NAME);
      const request = store.get(id);
      request.onsuccess = () => {
        if (request.result) store.put({ ...request.result, ...patch });
        resolve();
      };
      request.onerror = () => resolve();
    });
  }

  async clear(identity?: OfflineQueueIdentity): Promise<void> {
    const db = await this.ensureDB();
    if (!db) return;
    if (identity) {
      await Promise.all((await this.getAll(identity)).map((operation) => this.dequeue(operation.id)));
      return;
    }
    return new Promise<void>((resolve, reject) => {
      const request = db.transaction(STORE_NAME, 'readwrite').objectStore(STORE_NAME).clear();
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }
}

export const offlineQueue = new OfflineQueue();

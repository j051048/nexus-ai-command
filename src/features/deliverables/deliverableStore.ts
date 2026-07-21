import type { DeliverableAnnouncement, DeliverableRecord } from './types';

export const DELIVERABLE_READY_EVENT = 'nexus:deliverable-ready';

const STORAGE_PREFIX = 'nexus.deliverables';
const MAX_RECORDS = 40;
const runtimeDownloads = new Map<string, () => void | Promise<void>>();

export interface DeliverableEventDetail {
  record: DeliverableRecord;
  download?: () => void | Promise<void>;
}

function storageKey(scope: string) {
  return `${STORAGE_PREFIX}.${scope || 'personal'}`;
}

function isDeliverableRecord(value: unknown): value is DeliverableRecord {
  if (!value || typeof value !== 'object') return false;
  const record = value as Partial<DeliverableRecord>;
  return Boolean(
    record.id
      && record.title
      && record.filename
      && record.format
      && record.source
      && record.sourcePath
      && record.createdAt,
  );
}

export function readDeliverables(scope: string): DeliverableRecord[] {
  if (typeof window === 'undefined') return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(storageKey(scope)) || '[]') as unknown;
    return Array.isArray(parsed) ? parsed.filter(isDeliverableRecord).slice(0, MAX_RECORDS) : [];
  } catch {
    return [];
  }
}

export function writeDeliverables(scope: string, records: DeliverableRecord[]) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(storageKey(scope), JSON.stringify(records.slice(0, MAX_RECORDS)));
}

export function addDeliverable(scope: string, record: DeliverableRecord) {
  const next = [record, ...readDeliverables(scope).filter((item) => item.id !== record.id)]
    .slice(0, MAX_RECORDS);
  writeDeliverables(scope, next);
  return next;
}

export function removeDeliverable(scope: string, id: string) {
  runtimeDownloads.delete(id);
  const next = readDeliverables(scope).filter((item) => item.id !== id);
  writeDeliverables(scope, next);
  return next;
}

export function announceDeliverable(input: DeliverableAnnouncement) {
  const record: DeliverableRecord = {
    ...input,
    id: input.id || `deliverable-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    createdAt: input.createdAt || new Date().toISOString(),
  };
  if (input.download) runtimeDownloads.set(record.id, input.download);
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent<DeliverableEventDetail>(DELIVERABLE_READY_EVENT, {
      detail: { record, download: input.download },
    }));
  }
  return record;
}

export function getRuntimeDownload(id: string) {
  return runtimeDownloads.get(id);
}


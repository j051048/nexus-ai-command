export type DeliverableFormat = 'docx' | 'pdf' | 'xlsx' | 'png' | 'csv' | 'markdown';

export type DeliverableSource = 'assistant' | 'solution' | 'tender' | 'chart' | 'report';

export interface DeliverableDownloadAction {
  type: 'http-blob';
  url: string;
  filename: string;
  params?: Record<string, string>;
}

export interface DeliverableRecord {
  id: string;
  title: string;
  filename: string;
  format: DeliverableFormat;
  source: DeliverableSource;
  sourceLabel: string;
  sourcePath: string;
  createdAt: string;
  sizeBytes?: number;
  downloadAction?: DeliverableDownloadAction;
}

export interface DeliverableAnnouncement
  extends Omit<DeliverableRecord, 'id' | 'createdAt'> {
  id?: string;
  createdAt?: string;
  download?: () => void | Promise<void>;
}


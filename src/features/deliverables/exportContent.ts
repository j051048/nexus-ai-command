import { httpClient } from '@/lib/httpClient';

import type { DeliverableDownloadAction, DeliverableFormat } from './types';

const MIME_TYPES: Record<DeliverableFormat, string> = {
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  pdf: 'application/pdf',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  png: 'image/png',
  csv: 'text/csv;charset=utf-8',
  markdown: 'text/markdown;charset=utf-8',
};

interface ExportPayload {
  success: boolean;
  filename: string;
  content_base64: string;
  error?: string;
}

function safeFilename(value: string) {
  return value.replace(/[\\/:*?"<>|]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 72) || 'AI成果';
}

export function titleFromContent(content: string) {
  const heading = content.match(/^#{1,3}\s+(.+)$/m)?.[1];
  const firstLine = content.split('\n').map((line) => line.trim()).find(Boolean);
  return safeFilename((heading || firstLine || 'AI生成成果').replace(/[*_`#>]/g, '')).slice(0, 36);
}

function unwrapExportPayload(value: unknown): ExportPayload {
  const envelope = value as { data?: ExportPayload };
  const payload = envelope?.data || value as ExportPayload;
  if (!payload?.success || !payload.content_base64) {
    throw new Error(payload?.error || '文件生成失败');
  }
  return payload;
}

function base64ToBlob(base64: string, mimeType: string) {
  const binary = window.atob(base64);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new Blob([bytes], { type: mimeType });
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function markdownToPlainText(content: string) {
  return content
    .replace(/```[\s\S]*?```/g, (block) => block.replace(/```\w*/g, ''))
    .replace(/!\[[^\]]*]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/[*_`>]/g, '')
    .trim();
}

export function markdownTableRows(content: string): Array<Record<string, string | number>> {
  const lines = content.split('\n').map((line) => line.trim()).filter(Boolean);
  for (let index = 0; index < lines.length - 2; index += 1) {
    if (!lines[index].includes('|') || !/^\|?\s*:?-{3,}/.test(lines[index + 1])) continue;
    const cells = (line: string) => line.replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim());
    const headers = cells(lines[index]);
    const rows: Array<Record<string, string>> = [];
    for (let rowIndex = index + 2; rowIndex < lines.length && lines[rowIndex].includes('|'); rowIndex += 1) {
      const values = cells(lines[rowIndex]);
      rows.push(Object.fromEntries(headers.map((header, cellIndex) => [header || `列${cellIndex + 1}`, values[cellIndex] || ''])));
    }
    if (rows.length) return rows;
  }
  return markdownToPlainText(content)
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => ({ 序号: index + 1, 内容: line }));
}

async function exportImage(content: string, title: string) {
  const article = document.createElement('article');
  article.style.cssText = [
    'position:fixed', 'left:-10000px', 'top:0', 'width:1080px', 'padding:72px',
    'background:#ffffff', 'color:#101828', 'font-family:"Microsoft YaHei",sans-serif',
    'border-top:10px solid #1473e6', 'box-sizing:border-box', 'line-height:1.75',
  ].join(';');
  const heading = document.createElement('h1');
  heading.textContent = title;
  heading.style.cssText = 'font-size:38px;line-height:1.25;margin:0 0 32px;font-weight:700;';
  const body = document.createElement('div');
  body.textContent = markdownToPlainText(content).slice(0, 5000);
  body.style.cssText = 'white-space:pre-wrap;font-size:22px;';
  const footer = document.createElement('footer');
  footer.textContent = `Nexus AI · ${new Date().toLocaleDateString('zh-CN')}`;
  footer.style.cssText = 'margin-top:44px;padding-top:20px;border-top:1px solid #d9e0e8;color:#667085;font-size:16px;';
  article.append(heading, body, footer);
  document.body.appendChild(article);
  try {
    const html2canvas = (await import('html2canvas')).default;
    const canvas = await html2canvas(article, { scale: 1.5, backgroundColor: '#ffffff', logging: false });
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('图片生成失败')), 'image/png');
    });
  } finally {
    article.remove();
  }
}

export async function exportAIContent(content: string, format: 'docx' | 'pdf' | 'xlsx' | 'png') {
  const title = titleFromContent(content);
  if (format === 'png') {
    const blob = await exportImage(content, title);
    const filename = `${title}.png`;
    downloadBlob(blob, filename);
    return { filename, sizeBytes: blob.size };
  }

  const endpoint = format === 'xlsx' ? '/api/export/excel' : `/api/export/${format}`;
  const body = format === 'xlsx'
    ? { data: markdownTableRows(content), filename: title, sheet_name: 'AI成果' }
    : { content, filename: title, title, format_type: 'markdown' };
  const response = await httpClient.post(endpoint, body, { silentError: true });
  const payload = unwrapExportPayload(response.data);
  const blob = base64ToBlob(payload.content_base64, MIME_TYPES[format]);
  downloadBlob(blob, payload.filename);
  return { filename: payload.filename, sizeBytes: blob.size };
}

export async function repeatDownload(action: DeliverableDownloadAction) {
  const response = await httpClient.get(action.url, {
    params: action.params,
    responseType: 'blob',
    silentError: true,
  });
  downloadBlob(response.data as Blob, action.filename);
}


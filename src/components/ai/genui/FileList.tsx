import React from 'react';
import { File, FileText, Image, FileSpreadsheet } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileItem {
  name: string;
  size?: string;
  type?: string;
  status?: 'ready' | 'processing' | 'error' | 'done';
}

interface FileListProps {
  files: FileItem[];
  title?: string;
}

const statusConfig = {
  ready: {
    label: '就绪',
    className: 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400',
  },
  processing: {
    label: '处理中',
    className: 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300',
  },
  error: {
    label: '错误',
    className: 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300',
  },
  done: {
    label: '完成',
    className: 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300',
  },
};

function getFileIcon(type?: string) {
  if (!type) return File;

  const t = type.toLowerCase();
  if (t.includes('image') || t.includes('png') || t.includes('jpg') || t.includes('jpeg') || t.includes('gif') || t.includes('svg')) {
    return Image;
  }
  if (t.includes('spreadsheet') || t.includes('excel') || t.includes('csv') || t.includes('xlsx') || t.includes('xls')) {
    return FileSpreadsheet;
  }
  if (t.includes('text') || t.includes('doc') || t.includes('pdf') || t.includes('txt') || t.includes('md')) {
    return FileText;
  }
  return File;
}

function getFileIconColor(type?: string) {
  if (!type) return 'text-gray-400';

  const t = type.toLowerCase();
  if (t.includes('image') || t.includes('png') || t.includes('jpg') || t.includes('jpeg') || t.includes('gif') || t.includes('svg')) {
    return 'text-purple-500';
  }
  if (t.includes('spreadsheet') || t.includes('excel') || t.includes('csv') || t.includes('xlsx') || t.includes('xls')) {
    return 'text-green-500';
  }
  if (t.includes('text') || t.includes('doc') || t.includes('pdf') || t.includes('txt') || t.includes('md')) {
    return 'text-blue-500';
  }
  return 'text-gray-400';
}

export default function FileList({ files, title }: FileListProps) {
  if (!files || files.length === 0) return null;

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-3">{title}</h4>}
      <div className="rounded-lg border divide-y">
        {files.map((file, i) => {
          const IconComponent = getFileIcon(file.type);
          const iconColor = getFileIconColor(file.type);
          const status = file.status ? statusConfig[file.status] : null;

          return (
            <div
              key={i}
              className="flex items-center gap-3 p-3 hover:bg-muted/50 transition-colors"
            >
              {/* File icon */}
              <IconComponent className={cn('w-5 h-5 flex-shrink-0', iconColor)} />

              {/* File info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{file.name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  {file.type && (
                    <span className="text-xs text-muted-foreground uppercase">{file.type}</span>
                  )}
                  {file.size && (
                    <span className="text-xs text-muted-foreground">{file.size}</span>
                  )}
                </div>
              </div>

              {/* Status badge */}
              {status && (
                <span
                  className={cn(
                    'text-[10px] font-medium px-2 py-0.5 rounded-full flex-shrink-0',
                    status.className
                  )}
                >
                  {status.label}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

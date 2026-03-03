import React from 'react';
import { cn } from '@/lib/utils';

interface KanbanItem {
  id: string;
  title: string;
  subtitle?: string;
  tag?: string;
}

interface KanbanColumn {
  title: string;
  color?: string;
  items: KanbanItem[];
}

interface KanbanMiniProps {
  columns: KanbanColumn[];
  title?: string;
}

const defaultColumnColors = [
  { header: 'bg-gray-100 dark:bg-gray-800', dot: 'bg-gray-400' },
  { header: 'bg-blue-50 dark:bg-blue-950', dot: 'bg-blue-400' },
  { header: 'bg-amber-50 dark:bg-amber-950', dot: 'bg-amber-400' },
  { header: 'bg-green-50 dark:bg-green-950', dot: 'bg-green-400' },
  { header: 'bg-purple-50 dark:bg-purple-950', dot: 'bg-purple-400' },
  { header: 'bg-red-50 dark:bg-red-950', dot: 'bg-red-400' },
];

const tagColors = [
  'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300',
  'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300',
  'bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300',
  'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300',
  'bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300',
  'bg-pink-100 dark:bg-pink-900 text-pink-700 dark:text-pink-300',
];

function getTagColor(tag: string): string {
  // Simple hash to get a consistent color per tag
  let hash = 0;
  for (let i = 0; i < tag.length; i++) {
    hash = ((hash << 5) - hash + tag.charCodeAt(i)) | 0;
  }
  return tagColors[Math.abs(hash) % tagColors.length];
}

export default function KanbanMini({ columns, title }: KanbanMiniProps) {
  if (!columns || columns.length === 0) return null;

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-3">{title}</h4>}
      <div className="overflow-x-auto">
        <div className="inline-flex gap-3 min-w-fit pb-2">
          {columns.map((column, colIdx) => {
            const colorSet = defaultColumnColors[colIdx % defaultColumnColors.length];

            return (
              <div
                key={colIdx}
                className="w-56 flex-shrink-0 rounded-lg border bg-card overflow-hidden"
              >
                {/* Column header */}
                <div
                  className={cn(
                    'px-3 py-2 flex items-center gap-2 border-b',
                    column.color ? '' : colorSet.header
                  )}
                  style={column.color ? { backgroundColor: column.color + '20' } : undefined}
                >
                  <div
                    className={cn(
                      'w-2 h-2 rounded-full flex-shrink-0',
                      column.color ? '' : colorSet.dot
                    )}
                    style={column.color ? { backgroundColor: column.color } : undefined}
                  />
                  <span className="text-xs font-semibold truncate">{column.title}</span>
                  <span className="text-[10px] text-muted-foreground ml-auto">
                    {column.items.length}
                  </span>
                </div>

                {/* Column items */}
                <div className="p-2 flex flex-col gap-2 max-h-[300px] overflow-y-auto">
                  {column.items.length === 0 ? (
                    <div className="text-xs text-muted-foreground text-center py-4">
                      暂无项目
                    </div>
                  ) : (
                    column.items.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-md border bg-background p-2.5 shadow-sm hover:shadow transition-shadow"
                      >
                        <p className="text-xs font-medium leading-snug">{item.title}</p>
                        {item.subtitle && (
                          <p className="text-[11px] text-muted-foreground mt-1 leading-snug">
                            {item.subtitle}
                          </p>
                        )}
                        {item.tag && (
                          <span
                            className={cn(
                              'inline-block text-[10px] font-medium px-1.5 py-0.5 rounded mt-1.5',
                              getTagColor(item.tag)
                            )}
                          >
                            {item.tag}
                          </span>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

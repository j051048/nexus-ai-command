import React from 'react';
import { cn } from '@/lib/utils';

interface ComparisonTableProps {
  columns: Array<{ name: string; highlight?: boolean }>;
  rows: Array<{ label: string; values: string[] }>;
  title?: string;
}

export default function ComparisonTable({ columns, rows, title }: ComparisonTableProps) {
  if (!columns || columns.length === 0 || !rows || rows.length === 0) return null;

  const highlightIndex = columns.findIndex((col) => col.highlight);

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-3">{title}</h4>}
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="text-left p-3 font-medium text-muted-foreground min-w-[120px]">
                &nbsp;
              </th>
              {columns.map((col, i) => (
                <th
                  key={i}
                  className={cn(
                    'text-center p-3 font-semibold min-w-[120px]',
                    col.highlight && 'bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300'
                  )}
                >
                  <div className="flex flex-col items-center gap-1">
                    <span>{col.name}</span>
                    {col.highlight && (
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300">
                        推荐
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className={cn(
                  'border-b last:border-b-0',
                  rowIdx % 2 === 0 ? 'bg-background' : 'bg-muted/30'
                )}
              >
                <td className="p-3 font-medium text-muted-foreground">{row.label}</td>
                {row.values.map((val, colIdx) => (
                  <td
                    key={colIdx}
                    className={cn(
                      'text-center p-3',
                      colIdx === highlightIndex &&
                        'bg-green-50/50 dark:bg-green-950/50 font-medium text-green-700 dark:text-green-300'
                    )}
                  >
                    {val}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

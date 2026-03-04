import React, { useState, useMemo } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Column {
  key: string;
  label: string;
  align?: 'left' | 'center' | 'right';
}

interface DataTableProps {
  title?: string;
  columns: Column[];
  rows: Record<string, unknown>[];
  sortable?: boolean;
  maxRows?: number;
}

export function DataTable({
  title,
  columns,
  rows,
  sortable = true,
  maxRows = 20,
}: DataTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const sortedRows = useMemo(() => {
    const limited = rows.slice(0, maxRows);
    if (!sortKey) return limited;
    return [...limited].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === 'number' && typeof vb === 'number') {
        return sortDir === 'asc' ? va - vb : vb - va;
      }
      const sa = String(va);
      const sb = String(vb);
      return sortDir === 'asc' ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
  }, [rows, sortKey, sortDir, maxRows]);

  const handleSort = (key: string) => {
    if (!sortable) return;
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  if (!columns || columns.length === 0) return null;

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-3">{title}</h4>}
      <div className="overflow-x-auto border rounded-lg">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              {columns.map(col => (
                <th
                  key={col.key}
                  className={cn(
                    'px-3 py-3 font-medium text-muted-foreground whitespace-nowrap',
                    col.align === 'right' && 'text-right',
                    col.align === 'center' && 'text-center',
                    sortable && 'cursor-pointer hover:text-foreground select-none'
                  )}
                  onClick={() => handleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {sortable && sortKey === col.key ? (
                      sortDir === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />
                    ) : sortable ? (
                      <ArrowUpDown className="w-3 h-3 opacity-30" />
                    ) : null}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, i) => (
              <tr key={i} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                {columns.map(col => (
                  <td
                    key={col.key}
                    className={cn(
                      'px-3 py-2',
                      col.align === 'right' && 'text-right',
                      col.align === 'center' && 'text-center'
                    )}
                  >
                    {row[col.key] != null ? String(row[col.key]) : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > maxRows && (
        <p className="text-xs text-muted-foreground mt-2">
          显示前 {maxRows} 条，共 {rows.length} 条
        </p>
      )}
    </div>
  );
}

export default DataTable;

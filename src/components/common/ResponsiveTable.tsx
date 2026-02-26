/**
 * A7: 响应式表格组件
 * 移动端显示纵向信息卡片（可折叠展开），桌面端显示传统表格。
 * 当表格行数超过 virtualizeThreshold 时自动启用虚拟窗口化渲染。
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { cn } from '@/lib/utils';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export interface ColumnDef<T = Record<string, unknown>> {
  /** Column header label */
  header: React.ReactNode;
  /** Key in row data, or accessor function */
  accessor: keyof T | ((row: T) => React.ReactNode);
  /** Label shown in mobile card view */
  mobileLabel?: string;
  /** Hide this column on mobile cards */
  hideMobile?: boolean;
}

export interface ResponsiveTableProps<T = Record<string, unknown>> {
  headers: React.ReactNode[];
  /** Structured column definitions for enhanced mobile rendering */
  columns?: ColumnDef<T>[];
  rows: T[];
  renderCard: (row: T, index: number) => React.ReactNode;
  renderRow?: (row: T, index: number) => React.ReactNode;
  className?: string;
  emptyMessage?: React.ReactNode;
  /** Number of rows to show before "Load More" on mobile (default: 20) */
  mobilePageSize?: number;
  /** Enable virtual scrolling above this row count (default: 100) */
  virtualizeThreshold?: number;
}

/** Simple virtualization: only render rows visible in viewport + buffer */
function useVirtualRows<T>(rows: T[], rowHeight: number, containerRef: React.RefObject<HTMLDivElement | null>, enabled: boolean) {
  const [range, setRange] = useState({ start: 0, end: 50 });

  useEffect(() => {
    if (!enabled || !containerRef.current) return;
    const container = containerRef.current;
    const update = () => {
      const scrollTop = container.scrollTop;
      const viewportHeight = container.clientHeight;
      const buffer = 10;
      const start = Math.max(0, Math.floor(scrollTop / rowHeight) - buffer);
      const end = Math.min(rows.length, Math.ceil((scrollTop + viewportHeight) / rowHeight) + buffer);
      setRange({ start, end });
    };
    update();
    container.addEventListener('scroll', update, { passive: true });
    return () => container.removeEventListener('scroll', update);
  }, [enabled, rows.length, rowHeight, containerRef]);

  return enabled ? range : { start: 0, end: rows.length };
}

export function ResponsiveTable<T>({
  headers,
  columns,
  rows,
  renderCard,
  renderRow,
  className,
  emptyMessage = '暂无数据',
  mobilePageSize = 20,
  virtualizeThreshold = 100,
}: ResponsiveTableProps<T>) {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [mobileVisibleCount, setMobileVisibleCount] = useState(mobilePageSize);
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = !isMobile && rows.length > virtualizeThreshold;
  const ROW_HEIGHT = 48;
  const { start, end } = useVirtualRows(rows, ROW_HEIGHT, tableContainerRef, shouldVirtualize);

  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  const handleLoadMore = useCallback(() => {
    setMobileVisibleCount((prev) => Math.min(prev + mobilePageSize, rows.length));
  }, [mobilePageSize, rows.length]);

  if (rows.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        <p className="text-sm">{emptyMessage}</p>
      </div>
    );
  }

  // 移动端：纵向信息卡片列表 + 分页加载
  if (isMobile) {
    const visibleRows = rows.slice(0, mobileVisibleCount);
    return (
      <div className={cn('space-y-3', className)}>
        {visibleRows.map((row, index) => (
          <div key={index}>{renderCard(row, index)}</div>
        ))}
        {mobileVisibleCount < rows.length && (
          <button
            onClick={handleLoadMore}
            className="w-full rounded-lg border border-border py-2.5 text-sm text-muted-foreground hover:bg-accent transition-colors"
          >
            加载更多 ({rows.length - mobileVisibleCount} 条)
          </button>
        )}
      </div>
    );
  }

  // 桌面端：传统表格（大数据量时虚拟化）
  const totalHeight = shouldVirtualize ? rows.length * ROW_HEIGHT : undefined;
  const offsetY = shouldVirtualize ? start * ROW_HEIGHT : 0;
  const visibleRows = shouldVirtualize ? rows.slice(start, end) : rows;

  return (
    <div
      ref={tableContainerRef}
      className={cn('rounded-lg border border-border overflow-auto', className)}
      style={shouldVirtualize ? { maxHeight: 600, position: 'relative' } : undefined}
    >
      <Table>
        <TableHeader>
          <TableRow>
            {(columns ? columns.map((c) => c.header) : headers).map((header, index) => (
              <TableHead key={index}>{header}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {shouldVirtualize && (
            <tr style={{ height: offsetY }} aria-hidden="true" />
          )}
          {visibleRows.map((row, vIdx) => {
            const actualIndex = shouldVirtualize ? start + vIdx : vIdx;
            return (
              <TableRow key={actualIndex}>
                {renderRow ? (
                  renderRow(row, actualIndex)
                ) : (
                  Object.values(row as Record<string, unknown>).map((value, cellIndex) => (
                    <TableCell key={cellIndex}>{value as React.ReactNode}</TableCell>
                  ))
                )}
              </TableRow>
            );
          })}
          {shouldVirtualize && (
            <tr style={{ height: (rows.length - end) * ROW_HEIGHT }} aria-hidden="true" />
          )}
        </TableBody>
      </Table>
    </div>
  );
}

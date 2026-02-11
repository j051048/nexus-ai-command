/**
 * A7: 响应式表格组件
 * 移动端显示卡片列表，桌面端显示传统表格
 */

import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export interface ResponsiveTableProps<T = Record<string, unknown>> {
  headers: React.ReactNode[];
  rows: T[];
  renderCard: (row: T, index: number) => React.ReactNode;
  renderRow?: (row: T, index: number) => React.ReactNode;
  className?: string;
  emptyMessage?: React.ReactNode;
}

export function ResponsiveTable<T>({
  headers,
  rows,
  renderCard,
  renderRow,
  className,
  emptyMessage = '暂无数据',
}: ResponsiveTableProps<T>) {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  if (rows.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        <p className="text-sm">{emptyMessage}</p>
      </div>
    );
  }

  // 移动端：卡片列表
  if (isMobile) {
    return (
      <div className={cn('space-y-3', className)}>
        {rows.map((row, index) => (
          <div key={index}>{renderCard(row, index)}</div>
        ))}
      </div>
    );
  }

  // 桌面端：传统表格
  return (
    <div className={cn('rounded-lg border border-border overflow-hidden', className)}>
      <Table>
        <TableHeader>
          <TableRow>
            {headers.map((header, index) => (
              <TableHead key={index}>{header}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow key={index}>
              {renderRow ? (
                renderRow(row, index)
              ) : (
                Object.values(row).map((value, cellIndex) => (
                  <TableCell key={cellIndex}>{value as React.ReactNode}</TableCell>
                ))
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

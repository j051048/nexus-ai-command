import React from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// ==================== 基础骨架组件 ====================

export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('bg-card rounded-2xl p-6 border border-border', className)}>
      <Skeleton className="h-6 w-32 mb-4" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}

export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('bg-card rounded-2xl p-6 border border-border', className)}>
      <div className="flex justify-between items-center mb-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-8 w-24" />
      </div>
      <Skeleton className="h-64 w-full rounded-lg" />
    </div>
  );
}

export function StatCardSkeleton() {
  return (
    <div className="bg-card rounded-2xl p-4 border border-border">
      <div className="flex items-center justify-between mb-3">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-8 w-8 rounded-lg" />
      </div>
      <Skeleton className="h-8 w-24 mb-2" />
      <Skeleton className="h-3 w-16" />
    </div>
  );
}

export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
  return (
    <div className="flex items-center gap-4 py-4 px-4 border-b border-border">
      {Array.from({ length: columns }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn(
            'h-4',
            i === 0 ? 'w-32' : i === columns - 1 ? 'w-20' : 'w-24'
          )}
        />
      ))}
    </div>
  );
}

export function ListItemSkeleton() {
  return (
    <div className="flex items-center gap-4 py-3">
      <Skeleton className="h-10 w-10 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
      <Skeleton className="h-8 w-16 rounded-md" />
    </div>
  );
}

// ==================== 页面级骨架屏 ====================

export function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-32 rounded-xl" />
          <Skeleton className="h-10 w-24 rounded-xl" />
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatCardSkeleton key={i} />
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartSkeleton className="h-80" />
        <ChartSkeleton className="h-80" />
      </div>

      {/* Bottom Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CardSkeleton className="h-64" />
        <CardSkeleton className="h-64" />
      </div>
    </div>
  );
}

export function ProjectListSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>

      {/* AI Action Card */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center gap-4">
          <Skeleton className="h-12 w-12 rounded-full" />
          <div className="flex-1 space-y-3">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-full max-w-md" />
            <div className="flex gap-2">
              <Skeleton className="h-10 flex-1 max-w-lg rounded-xl" />
              <Skeleton className="h-10 w-24 rounded-xl" />
            </div>
          </div>
        </div>
      </div>

      {/* Project Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-card rounded-2xl p-6 border border-border space-y-4">
            <div className="flex justify-between">
              <div className="space-y-2">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-3 w-24" />
              </div>
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
            <Skeleton className="h-10 w-full" />
            <div className="space-y-2">
              <div className="flex justify-between">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-3 w-8" />
              </div>
              <Skeleton className="h-2 w-full rounded-full" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ApprovalListSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-10 w-10 rounded-full" />
      </div>

      {/* Tabs */}
      <Skeleton className="h-10 w-64 rounded-lg" />

      {/* List */}
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="bg-card rounded-xl p-4 border border-border flex items-center gap-4"
          >
            <Skeleton className="h-12 w-12 rounded-xl" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-4 w-32" />
            </div>
            <div className="flex items-center gap-2">
              <Skeleton className="h-8 w-16 rounded-md" />
              <Skeleton className="h-8 w-16 rounded-md" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChatSkeleton() {
  return (
    <div className="space-y-4 p-4 animate-pulse">
      {/* Messages */}
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className={cn('flex gap-3', i % 2 === 0 ? 'justify-start' : 'justify-end')}
        >
          {i % 2 === 0 && <Skeleton className="h-8 w-8 rounded-lg flex-shrink-0" />}
          <Skeleton
            className={cn(
              'h-16 rounded-2xl',
              i % 2 === 0 ? 'w-64 rounded-bl-md' : 'w-48 rounded-br-md'
            )}
          />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 5, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div className="bg-card rounded-xl border border-border overflow-hidden animate-pulse">
      {/* Header */}
      <div className="flex items-center gap-4 py-3 px-4 bg-muted/50 border-b border-border">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 w-20" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <TableRowSkeleton key={i} columns={columns} />
      ))}
    </div>
  );
}

export function KanbanSkeleton() {
  return (
    <div className="flex gap-4 overflow-x-auto pb-4 animate-pulse">
      {Array.from({ length: 4 }).map((_, colIndex) => (
        <div
          key={colIndex}
          className="flex-shrink-0 w-72 bg-muted/30 rounded-xl p-4 space-y-3"
        >
          <div className="flex items-center justify-between mb-4">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-5 w-6 rounded-full" />
          </div>
          {Array.from({ length: 3 }).map((_, cardIndex) => (
            <div
              key={cardIndex}
              className="bg-card rounded-lg p-4 border border-border space-y-3"
            >
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-3 w-3/4" />
              <div className="flex items-center justify-between pt-2">
                <Skeleton className="h-6 w-6 rounded-full" />
                <Skeleton className="h-4 w-16" />
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export default {
  CardSkeleton,
  ChartSkeleton,
  StatCardSkeleton,
  TableRowSkeleton,
  ListItemSkeleton,
  DashboardSkeleton,
  ProjectListSkeleton,
  ApprovalListSkeleton,
  ChatSkeleton,
  TableSkeleton,
  KanbanSkeleton,
};
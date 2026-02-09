import React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Plus, Search, FileX, Inbox, FolderOpen } from 'lucide-react';

export type EmptyStateType = 'default' | 'search' | 'error' | 'no-data' | 'no-permission';

interface EmptyStateProps {
  type?: EmptyStateType;
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  suggestions?: string[];
  className?: string;
  compact?: boolean;
}

const defaultIcons: Record<EmptyStateType, React.ReactNode> = {
  default: <Inbox className="w-12 h-12 text-muted-foreground/50" />,
  search: <Search className="w-12 h-12 text-muted-foreground/50" />,
  error: <FileX className="w-12 h-12 text-destructive/50" />,
  'no-data': <FolderOpen className="w-12 h-12 text-muted-foreground/50" />,
  'no-permission': <FileX className="w-12 h-12 text-warning/50" />,
};

export function EmptyState({
  type = 'default',
  icon,
  title,
  description,
  action,
  secondaryAction,
  suggestions,
  className,
  compact = false,
}: EmptyStateProps) {
  const displayIcon = icon || defaultIcons[type];

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center',
        compact ? 'py-8 px-4' : 'py-16 px-6',
        className
      )}
    >
      {/* Icon Container */}
      <div
        className={cn(
          'rounded-full bg-muted/50 flex items-center justify-center mb-4 transition-transform hover:scale-105',
          compact ? 'w-16 h-16' : 'w-20 h-20'
        )}
      >
        {displayIcon}
      </div>

      {/* Title */}
      <h3
        className={cn(
          'font-semibold text-foreground mb-2',
          compact ? 'text-base' : 'text-xl'
        )}
      >
        {title}
      </h3>

      {/* Description */}
      {description && (
        <p
          className={cn(
            'text-muted-foreground max-w-md mb-6',
            compact ? 'text-sm' : 'text-base'
          )}
        >
          {description}
        </p>
      )}

      {/* Suggestions */}
      {suggestions && suggestions.length > 0 && (
        <div className="mb-6 text-left">
          <p className="text-sm text-muted-foreground mb-2 text-center">您可以尝试：</p>
          <ul className="space-y-1.5">
            {suggestions.map((suggestion, index) => (
              <li
                key={index}
                className="flex items-center gap-2 text-sm text-muted-foreground"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />
                <span>{suggestion}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3">
        {action && (
          <Button onClick={action.onClick} size={compact ? 'sm' : 'default'}>
            {action.icon || <Plus className="w-4 h-4 mr-2" />}
            {action.label}
          </Button>
        )}
        {secondaryAction && (
          <Button
            variant="outline"
            onClick={secondaryAction.onClick}
            size={compact ? 'sm' : 'default'}
          >
            {secondaryAction.label}
          </Button>
        )}
      </div>
    </div>
  );
}

// 预设的空状态变体
export function NoSearchResults({
  query,
  onClear,
}: {
  query: string;
  onClear: () => void;
}) {
  return (
    <EmptyState
      type="search"
      title={`未找到 "${query}" 相关结果`}
      description="请尝试其他关键词或调整筛选条件"
      action={{
        label: '清除搜索',
        onClick: onClear,
        icon: <Search className="w-4 h-4 mr-2" />,
      }}
      suggestions={[
        '检查关键词是否有拼写错误',
        '尝试使用更简短的关键词',
        '减少筛选条件',
      ]}
    />
  );
}

export function NoDataYet({
  resourceName,
  onAdd,
}: {
  resourceName: string;
  onAdd?: () => void;
}) {
  return (
    <EmptyState
      type="no-data"
      title={`暂无${resourceName}`}
      description={`还没有任何${resourceName}，立即创建第一个吧`}
      action={
        onAdd
          ? {
              label: `新建${resourceName}`,
              onClick: onAdd,
            }
          : undefined
      }
    />
  );
}

export function LoadingError({
  message,
  onRetry,
}: {
  message?: string;
  onRetry: () => void;
}) {
  return (
    <EmptyState
      type="error"
      title="加载失败"
      description={message || '数据加载时发生错误，请稍后重试'}
      action={{
        label: '重新加载',
        onClick: onRetry,
        icon: <span className="mr-2">🔄</span>,
      }}
    />
  );
}

export default EmptyState;
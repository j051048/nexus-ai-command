import { Search } from "lucide-react";
import { WorkEmptyState } from '@/components/common/WorkState';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <WorkEmptyState
      className={className}
      density="compact"
      icon={icon}
      title={title}
      description={description}
      actionLabel={action?.label}
      onAction={action?.onClick}
    />
  );
}

export const NoDataYet = ({
  title,
  description,
  resourceName,
  onAdd,
  ...props
}: Partial<EmptyStateProps> & { resourceName?: string; onAdd?: () => void }) => (
  <EmptyState
    title={title ?? (resourceName ? `暂无${resourceName}` : "暂无数据")}
    description={description ?? (resourceName ? `目前还没有${resourceName}数据，可以先创建一条记录。` : "目前还没有相关数据。")}
    action={onAdd ? { label: `新建${resourceName || '数据'}`, onClick: onAdd } : undefined}
    {...props}
  />
);

export const NoSearchResults = ({
  title = "未找到结果",
  description = "没有找到匹配的搜索结果，请尝试其他关键词。",
  query,
  onClear,
  ...props
}: Partial<EmptyStateProps> & { query?: string; onClear?: () => void }) => (
  <EmptyState
    icon={<Search className="w-10 h-10" />}
    title={title}
    description={query ? `未找到“${query}”的相关结果，请尝试其他关键词。` : description}
    action={onClear ? { label: "清除搜索", onClick: onClear } : undefined}
    {...props}
  />
);

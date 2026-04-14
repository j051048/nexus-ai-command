import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

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
    <div className={cn("flex flex-col items-center justify-center py-16 px-4", className)}>
      {icon && (
        <div className="w-24 h-24 rounded-full bg-muted/50 flex items-center justify-center mb-6 text-muted-foreground">
          {icon}
        </div>
      )}
      <h3 className="text-heading-sm mb-2">{title}</h3>
      <p className="text-body-sm text-muted-foreground text-center max-w-md mb-6">
        {description}
      </p>
      {action && (
        <Button onClick={action.onClick} size="lg">
          {action.label}
        </Button>
      )}
    </div>
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
    description={description ?? (resourceName ? `目前还没有${resourceName}数据，点击上方按钮创建。` : "目前还没有相关数据，请稍后再试。")}
    action={onAdd ? { label: `新建${resourceName || '数据'}`, onClick: onAdd } : undefined}
    {...props}
  />
);

export const NoSearchResults = ({
  title = "未找到结果",
  description = "没找到匹配的搜索结果，请尝试其他关键词。",
  query,
  onClear,
  ...props
}: Partial<EmptyStateProps> & { query?: string; onClear?: () => void }) => (
  <EmptyState
    icon={<Search className="w-10 h-10" />}
    title={title}
    description={query ? `未找到"${query}"的相关结果，请尝试其他关键词。` : description}
    action={onClear ? { label: "清除搜索", onClick: onClear } : undefined}
    {...props}
  />
);

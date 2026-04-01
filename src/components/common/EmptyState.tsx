import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      {icon && (
        <div className="w-24 h-24 rounded-full bg-muted/50 flex items-center justify-center mb-6">
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

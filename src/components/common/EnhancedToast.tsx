import React from 'react';
import { AlertCircle, CheckCircle2, Info, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type ToastType = 'info' | 'success' | 'warning' | 'error';

interface EnhancedToastProps {
  type: ToastType;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

const icons = {
  info: Info,
  success: CheckCircle2,
  warning: AlertCircle,
  error: XCircle,
};

const styles = {
  info: 'bg-blue-50 border-blue-200 text-blue-900',
  success: 'bg-green-50 border-green-200 text-green-900',
  warning: 'bg-orange-50 border-orange-200 text-orange-900',
  error: 'bg-red-50 border-red-200 text-red-900',
};

export function EnhancedToast({ type, title, description, action }: EnhancedToastProps) {
  const Icon = icons[type];

  return (
    <div className={cn('rounded-lg border p-4 shadow-lg', styles[type])}>
      <div className="flex items-start gap-3">
        <Icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm">{title}</p>
          {description && (
            <p className="text-sm opacity-90 mt-1">{description}</p>
          )}
          {action && (
            <Button
              size="sm"
              variant="outline"
              onClick={action.onClick}
              className="mt-2"
            >
              {action.label}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

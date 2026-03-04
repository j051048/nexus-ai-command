import React from 'react';
import { AlertTriangle, Info, CheckCircle, XCircle } from 'lucide-react';

type AlertLevel = 'info' | 'warning' | 'success' | 'error';

interface AlertItem {
  level: AlertLevel;
  title: string;
  message?: string;
}

interface AlertListProps {
  title?: string;
  alerts: AlertItem[];
}

const ICON_MAP = {
  info: Info,
  warning: AlertTriangle,
  success: CheckCircle,
  error: XCircle,
};

const COLOR_MAP = {
  info: 'text-blue-600 dark:text-blue-400 bg-blue-500/10',
  warning: 'text-yellow-600 dark:text-yellow-400 bg-yellow-500/10',
  success: 'text-green-600 dark:text-green-400 bg-green-500/10',
  error: 'text-red-600 dark:text-red-400 bg-red-500/10',
};

export default function AlertList({ title, alerts = [] }: AlertListProps) {
  return (
    <div className="p-4 space-y-3">
      {title && <h3 className="text-sm font-semibold text-foreground">{title}</h3>}
      {alerts.map((alert, i) => {
        const Icon = ICON_MAP[alert.level] || Info;
        const color = COLOR_MAP[alert.level] || COLOR_MAP.info;
        return (
          <div key={i} className={`flex items-start gap-3 rounded-lg p-3 ${color}`}>
            <Icon className="w-4 h-4 mt-0.5 shrink-0" />
            <div className="space-y-0.5">
              <div className="text-sm font-medium">{alert.title}</div>
              {alert.message && <div className="text-xs opacity-80">{alert.message}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

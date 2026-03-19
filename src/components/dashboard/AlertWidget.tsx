import { useEffect, useState } from 'react';
import { AlertTriangle, AlertCircle, Info, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { aiClient } from '@/api/aiClient';

interface AlertItem {
  type: string;
  severity: 'error' | 'warning' | 'info';
  title: string;
  message: string;
  items?: Record<string, unknown>[];
  action_url?: string;
}

const severityConfig = {
  error: { icon: AlertCircle, bg: 'bg-destructive/10', border: 'border-destructive/30', text: 'text-destructive' },
  warning: { icon: AlertTriangle, bg: 'bg-warning/10', border: 'border-warning/30', text: 'text-warning' },
  info: { icon: Info, bg: 'bg-primary/10', border: 'border-primary/30', text: 'text-primary' },
};

export function AlertWidget() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    aiClient.get('/api/dashboard/alerts')
      .then((res) => {
        const data = (res as { data?: AlertItem[] })?.data || [];
        setAlerts(data);
      })
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return null;
  if (alerts.length === 0) return null;

  return (
    <div className="space-y-3">
      {alerts.map((alert, i) => {
        const config = severityConfig[alert.severity] || severityConfig.info;
        const Icon = config.icon;
        return (
          <div
            key={`${alert.type}-${i}`}
            className={cn(
              'flex items-start gap-3 p-4 rounded-xl border transition-all',
              config.bg, config.border,
            )}
          >
            <Icon className={cn('w-5 h-5 mt-0.5 shrink-0', config.text)} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <h4 className="font-semibold text-sm">{alert.title}</h4>
                {alert.action_url && (
                  <a
                    href={alert.action_url}
                    className={cn('flex items-center gap-1 text-xs hover:underline', config.text)}
                  >
                    查看 <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
              <p className="text-sm text-muted-foreground mt-0.5">{alert.message}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

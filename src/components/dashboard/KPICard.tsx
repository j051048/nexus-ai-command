import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string | number;
  change?: number;
  trend?: 'up' | 'down';
  icon?: React.ReactNode;
}

export function KPICard({ title, value, change, trend, icon }: KPICardProps) {
  return (
    <div className="glass-card p-6 rounded-xl">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-body-sm text-muted-foreground">{title}</p>
          <h3 className="text-heading-lg mt-1">{value}</h3>
        </div>
        {icon && (
          <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
            {icon}
          </div>
        )}
      </div>

      {change !== undefined && (
        <div className={cn(
          "flex items-center gap-1 text-body-sm",
          trend === 'up' ? 'text-success' : 'text-destructive'
        )}>
          {trend === 'up' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          <span>{Math.abs(change)}% vs 上周</span>
        </div>
      )}
    </div>
  );
}

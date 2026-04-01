import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FilterConfig {
  type: 'search' | 'select';
  key: string;
  label: string;
  placeholder?: string;
  options?: { value: string; label: string }[];
}

interface FilterPanelProps {
  filters: FilterConfig[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onReset: () => void;
  className?: string;
}

export function FilterPanel({ filters, values, onChange, onReset, className }: FilterPanelProps) {
  const hasActiveFilters = Object.values(values).some(v => v && v !== 'all');

  return (
    <Card className={cn('p-4', className)}>
      <div className="flex flex-wrap gap-3 items-end">
        {filters.map(filter => (
          <div key={filter.key} className="flex-1 min-w-[200px]">
            <label className="text-sm font-medium mb-1.5 block">{filter.label}</label>
            {filter.type === 'search' ? (
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder={filter.placeholder}
                  value={values[filter.key] || ''}
                  onChange={(e) => onChange(filter.key, e.target.value)}
                  className="pl-9"
                />
              </div>
            ) : (
              <Select value={values[filter.key] || 'all'} onValueChange={(v) => onChange(filter.key, v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  {filter.options?.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        ))}

        {hasActiveFilters && (
          <Button variant="outline" size="default" onClick={onReset} className="gap-2">
            <X className="w-4 h-4" />
            重置
          </Button>
        )}
      </div>
    </Card>
  );
}

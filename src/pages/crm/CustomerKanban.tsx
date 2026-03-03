import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { useUpdateCustomer } from '@/hooks/useCRM';
import type { Customer } from '@/hooks/useCRM';
import { STAGES } from './constants';

function CustomerCard({ customer, onClick }: { customer: Customer; onClick: () => void }) {
  const stage = STAGES[customer.stage] || STAGES.lead;
  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={onClick}>
      <CardContent className="p-4 space-y-2">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <h4 className="font-medium truncate">{customer.name}</h4>
            <p className="text-xs text-muted-foreground truncate">{customer.company}</p>
          </div>
          <Badge className={cn('shrink-0 text-xs', stage.color, stage.bg)}>{stage.name}</Badge>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{customer.industry}</span>
          {customer.estimated_value > 0 && (
            <span className="font-medium">{'\u00A5'}{Number(customer.estimated_value).toLocaleString()}</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export interface CustomerKanbanProps {
  customers: Customer[];
  onSelect: (c: Customer) => void;
}

export default function CustomerKanban({ customers, onSelect }: CustomerKanbanProps) {
  const columns = ['lead', 'prospect', 'opportunity', 'customer'];
  const updateMutation = useUpdateCustomer();

  const handleStageChange = (e: React.MouseEvent, customer: Customer, newStage: string) => {
    e.stopPropagation();
    if (newStage !== customer.stage) {
      updateMutation.mutate({ id: customer.id, data: { stage: newStage } });
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {columns.map(stageKey => {
        const stage = STAGES[stageKey];
        const stageCustomers = customers.filter(c => c.stage === stageKey);
        return (
          <div key={stageKey} className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className={cn('font-medium text-sm', stage.color)}>{stage.name}</h3>
              <Badge variant="outline" className="text-xs">{stageCustomers.length}</Badge>
            </div>
            <div className="space-y-2 min-h-[200px]">
              {stageCustomers.map(c => (
                <div key={c.id} className="relative group">
                  <CustomerCard customer={c} onClick={() => onSelect(c)} />
                  <div className="absolute bottom-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity" onClick={e => e.stopPropagation()}>
                    <Select value={c.stage} onValueChange={(v) => handleStageChange({ stopPropagation: () => {} } as React.MouseEvent, c, v)}>
                      <SelectTrigger className="h-6 w-[80px] text-xs bg-background/90 backdrop-blur-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(STAGES).filter(([k]) => k !== 'churned').map(([key, val]) => (
                          <SelectItem key={key} value={key} className="text-xs">{val.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              ))}
              {stageCustomers.length === 0 && (
                <div className="text-center py-8 text-sm text-muted-foreground border border-dashed rounded-lg">
                  暂无客户
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

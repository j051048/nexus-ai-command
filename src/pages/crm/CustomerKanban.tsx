import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useUpdateCustomer } from '@/hooks/useCRM';
import type { Customer } from '@/hooks/useCRM';
import { STAGES } from './constants';
import { DragDropContext, Droppable, Draggable, DropResult, DraggableProvided } from '@hello-pangea/dnd';
import { Briefcase, CreditCard, Flame, UserCheck, GripVertical } from 'lucide-react';

const COLUMN_CONFIG: Record<string, { icon: React.ReactNode }> = {
  lead: { icon: <Flame className="w-4 h-4" /> },
  prospect: { icon: <Briefcase className="w-4 h-4" /> },
  opportunity: { icon: <CreditCard className="w-4 h-4" /> },
  customer: { icon: <UserCheck className="w-4 h-4" /> },
};

function CustomerCard({ 
  customer, 
  onClick, 
  provided, 
  isDragging 
}: { 
  customer: Customer; 
  onClick: () => void; 
  provided: DraggableProvided;
  isDragging: boolean;
}) {
  const stage = STAGES[customer.stage] || STAGES.lead;
  
  return (
    <div
      ref={provided.innerRef}
      {...provided.draggableProps}
      {...provided.dragHandleProps}
      className={cn(
        "mb-3 transition-all duration-200 outline-none",
        isDragging && "rotate-2 scale-105 z-50"
      )}
    >
      <Card 
        className={cn(
          "cursor-grab active:cursor-grabbing hover:shadow-lg transition-all border-l-4",
          stage.border,
          isDragging ? "shadow-2xl ring-2 ring-primary/20" : "hover:border-primary/50"
        )} 
        onClick={onClick}
      >
        <CardContent className="p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h4 className="font-bold text-sm tracking-tight truncate group-hover:text-primary transition-colors">
                {customer.name}
              </h4>
              <p className="text-[10px] text-muted-foreground uppercase font-mono tracking-wider truncate py-0.5">
                {customer.company}
              </p>
            </div>
            <GripVertical className="w-3.5 h-3.5 text-muted-foreground/30 shrink-0 mt-1" />
          </div>

          <div className="flex items-center justify-between mt-auto">
            <div className="flex items-center gap-1.5 min-w-0">
               <Badge className={cn('shrink-0 text-[10px] px-1.5 py-0 h-4 font-bold uppercase', stage.color, stage.bg)}>
                 {stage.name}
               </Badge>
            </div>
            {customer.estimated_value > 0 && (
              <span className="font-mono font-bold text-[11px] text-foreground bg-secondary/50 px-1.5 py-0.5 rounded tabular-nums">
                ¥{Number(customer.estimated_value).toLocaleString()}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export interface CustomerKanbanProps {
  customers: Customer[];
  onSelect: (c: Customer) => void;
}

export default function CustomerKanban({ customers, onSelect }: CustomerKanbanProps) {
  const columns = ['lead', 'prospect', 'opportunity', 'customer'];
  const updateMutation = useUpdateCustomer();

  const onDragEnd = (result: DropResult) => {
    const { destination, source, draggableId } = result;

    if (!destination || (destination.droppableId === source.droppableId && destination.index === source.index)) {
      return;
    }

    const customerId = draggableId;
    const newStage = destination.droppableId;
    
    updateMutation.mutate({ id: customerId, data: { stage: newStage } });
  };

  return (
    <DragDropContext onDragEnd={onDragEnd}>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 min-h-[600px]">
        {columns.map(stageKey => {
          const stage = STAGES[stageKey];
          const stageCustomers = customers.filter(c => c.stage === stageKey);
          const config = COLUMN_CONFIG[stageKey];

          return (
            <div key={stageKey} className="flex flex-col bg-secondary/10 rounded-2xl border border-border/50 overflow-hidden">
              <div className="p-4 border-b border-border/30 bg-background/40 backdrop-blur-sm flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={cn("p-1.5 rounded-lg bg-background shadow-inner", stage.color)}>
                    {config.icon}
                  </div>
                  <h3 className="font-bold text-sm tracking-tight">{stage.name}</h3>
                </div>
                <Badge variant="secondary" className="font-mono text-[10px] tabular-nums bg-background/50 border-none">
                  {stageCustomers.length}
                </Badge>
              </div>

              <Droppable droppableId={stageKey}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={cn(
                      "flex-1 p-3 transition-colors duration-200 min-h-[400px]",
                      snapshot.isDraggingOver ? "bg-primary/5" : "bg-transparent"
                    )}
                  >
                    {stageCustomers.map((c, index) => (
                      <Draggable key={c.id} draggableId={c.id} index={index}>
                        {(provided, snapshot) => (
                          <CustomerCard 
                            customer={c} 
                            onClick={() => onSelect(c)} 
                            provided={provided}
                            isDragging={snapshot.isDragging}
                          />
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}

                    {stageCustomers.length === 0 && !snapshot.isDraggingOver && (
                      <div className="h-full flex flex-col items-center justify-center py-20 text-muted-foreground/30 opacity-40 select-none">
                        <div className="w-12 h-12 rounded-full border-2 border-dashed border-current flex items-center justify-center mb-3">
                            {config.icon}
                        </div>
                        <p className="text-[10px] font-bold uppercase tracking-widest">拖拽客户至此</p>
                      </div>
                    )}
                  </div>
                )}
              </Droppable>

              {stageCustomers.length > 0 && (
                 <div className="px-4 py-2 bg-background/20 border-t border-border/20 text-[10px] text-muted-foreground flex justify-between uppercase font-bold tracking-tighter">
                    <span>预估总额</span>
                    <span className="text-foreground font-mono">
                        ¥{stageCustomers.reduce((acc, c) => acc + (c.estimated_value || 0), 0).toLocaleString()}
                    </span>
                 </div>
              )}
            </div>
          );
        })}
      </div>
    </DragDropContext>
  );
}

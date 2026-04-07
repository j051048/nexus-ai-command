import React, { useState, useCallback } from 'react';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { MoreVertical, Tag, DollarSign, Calendar } from 'lucide-react';

interface KanbanItem {
  id: string;
  title: string;
  subtitle?: string;
  tag?: string;
  amount?: string;
  date?: string;
}

interface KanbanColumn {
  id: string;
  title: string;
  color?: string;
  items: KanbanItem[];
}

interface KanbanMiniProps {
  columns: KanbanColumn[];
  title?: string;
  onSendMessage?: (prompt: string) => void;
}

const defaultColumnColors = [
  { header: 'bg-slate-100/50 dark:bg-slate-800/50', dot: 'bg-slate-400' },
  { header: 'bg-blue-50/50 dark:bg-blue-900/20', dot: 'bg-blue-400' },
  { header: 'bg-amber-50/50 dark:bg-amber-900/20', dot: 'bg-amber-400' },
  { header: 'bg-emerald-50/50 dark:bg-emerald-900/20', dot: 'bg-emerald-400' },
];

export default function KanbanMini({ columns: initialColumns, title, onSendMessage }: KanbanMiniProps) {
  const [columns, setColumns] = useState<KanbanColumn[]>(initialColumns);

  const onDragEnd = (result: DropResult) => {
    const { source, destination, draggableId } = result;

    if (!destination) return;
    if (source.droppableId === destination.droppableId && source.index === destination.index) return;

    const sourceColIndex = columns.findIndex(c => c.id === source.droppableId);
    const destColIndex = columns.findIndex(c => c.id === destination.droppableId);
    
    if (sourceColIndex === -1 || destColIndex === -1) return;

    const sourceSteps = [...columns[sourceColIndex].items];
    const destSteps = source.droppableId === destination.droppableId 
      ? sourceSteps 
      : [...columns[destColIndex].items];

    const [movedItem] = sourceSteps.splice(source.index, 1);
    destSteps.splice(destination.index, 0, movedItem);

    const newColumns = [...columns];
    newColumns[sourceColIndex] = { ...newColumns[sourceColIndex], items: sourceSteps };
    newColumns[destColIndex] = { ...newColumns[destColIndex], items: destSteps };

    setColumns(newColumns);

    // AI Feedback
    if (onSendMessage && source.droppableId !== destination.droppableId) {
      onSendMessage(`我已将商机「${movedItem.title}」从「${columns[sourceColIndex].title}」移动到了「${columns[destColIndex].title}」阶段。`);
    }
  };

  if (!columns?.length) return null;

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center justify-between px-1">
        {title && <h4 className="text-sm font-bold text-foreground/80">{title}</h4>}
        <div className="flex -space-x-2">
           {[1,2,3].map(i => (
             <div key={i} className="h-5 w-5 rounded-full border-2 border-background bg-muted flex items-center justify-center text-[8px] font-bold">U{i}</div>
           ))}
        </div>
      </div>

      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
          {columns.map((column, colIdx) => (
            <div key={column.id} className="w-64 flex-shrink-0 flex flex-col gap-3">
              {/* Header */}
              <div className={cn(
                "flex items-center justify-between px-3 py-2 rounded-lg border bg-card/40 backdrop-blur-md shadow-sm",
                column.color ? "" : defaultColumnColors[colIdx % 4].header
              )}>
                <div className="flex items-center gap-2 max-w-[80%]">
                  <div className={cn("h-2 w-2 rounded-full", defaultColumnColors[colIdx % 4].dot)} />
                  <span className="text-[11px] font-bold truncate">{column.title}</span>
                </div>
                <span className="text-[10px] tabular-nums font-mono bg-background/50 px-1.5 py-0.5 rounded border">{column.items.length}</span>
              </div>

              {/* Droppable Area */}
              <Droppable droppableId={column.id}>
                {(provided, snapshot) => (
                  <div
                    {...provided.droppableProps}
                    ref={provided.innerRef}
                    className={cn(
                      "flex-1 min-h-[150px] rounded-xl p-2 transition-colors duration-200",
                      snapshot.isDraggingOver ? "bg-accent/30 ring-2 ring-blue-500/10" : "bg-muted/30"
                    )}
                  >
                    {column.items.map((item, index) => (
                      <Draggable key={item.id} draggableId={item.id} index={index}>
                        {(provided, snapshot) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            {...provided.dragHandleProps}
                            className={cn(
                              "mb-3 rounded-xl border bg-background p-3 shadow-sm hover:shadow-md hover:border-blue-500/30 transition-all",
                              snapshot.isDragging && "rotate-2 scale-105 shadow-xl ring-2 ring-blue-500"
                            )}
                          >
                            <div className="flex justify-between items-start mb-2">
                               <p className="text-xs font-bold leading-tight line-clamp-1">{item.title}</p>
                               <MoreVertical className="h-3 w-3 text-muted-foreground opacity-40" />
                            </div>
                            
                            {item.subtitle && (
                              <p className="text-[10px] text-muted-foreground mb-2">{item.subtitle}</p>
                            )}

                            <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-dashed border-border/60">
                               {item.amount && (
                                 <div className="flex items-center gap-1 text-[9px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-500/5 px-1 rounded">
                                   <DollarSign className="h-2 w-2" />
                                   {item.amount}
                                 </div>
                               )}
                               {item.date && (
                                 <div className="flex items-center gap-1 text-[9px] text-muted-foreground">
                                   <Calendar className="h-2 w-2" />
                                   {item.date}
                                 </div>
                               )}
                               {item.tag && (
                                  <div className="flex items-center gap-1 text-[9px] bg-blue-500/5 text-blue-600 dark:text-blue-400 px-1 rounded">
                                    <Tag className="h-2 w-2" />
                                    {item.tag}
                                  </div>
                               )}
                            </div>
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </div>
          ))}
        </div>
      </DragDropContext>
    </div>
  );
}

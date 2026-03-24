import React, { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  MoreHorizontal,
  Eye,
  Pencil,
  Trash2,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { Customer } from '@/hooks/useCRM';
import { STAGES } from './constants';

export interface CustomerTableProps {
  customers: Customer[];
  onSelect: (c: Customer) => void;
  onEdit: (c: Customer) => void;
  onDelete: (c: Customer) => void;
}

export default function CustomerTable({
  customers,
  onSelect,
  onEdit,
  onDelete,
}: CustomerTableProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  // The virtualizer handles large lists efficiently by only rendering items in view
  const rowVirtualizer = useVirtualizer({
    count: customers.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 64, // Estimated height of each row in px
    overscan: 5,
  });

  return (
    <div className="space-y-2">
      {/* Table Header - Fixed */}
      <div className="grid grid-cols-3 md:grid-cols-7 lg:grid-cols-12 gap-2 px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider border-b">
        <div className="col-span-1 md:col-span-2 lg:col-span-3">客户名称</div>
        <div className="hidden md:block md:col-span-1 lg:col-span-2">公司</div>
        <div className="hidden md:block md:col-span-1 lg:col-span-1">行业</div>
        <div className="col-span-1 md:col-span-1 lg:col-span-1 text-center">阶段</div>
        <div className="hidden md:block md:col-span-1 lg:col-span-2 text-right">预估金额</div>
        <div className="hidden lg:block lg:col-span-2">来源</div>
        <div className="col-span-1 md:col-span-1 lg:col-span-1 text-right">操作</div>
      </div>

      {/* Virtualized Container */}
      <div
        ref={parentRef}
        className="h-[calc(100vh-20rem)] min-h-[400px] overflow-auto custom-scrollbar-minimal"
        style={{
          contain: 'strict',
        }}
      >
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const c = customers[virtualRow.index];
            const stage = STAGES[c.stage] || STAGES.lead;
            
            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={rowVirtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className={cn(
                  "grid grid-cols-3 md:grid-cols-7 lg:grid-cols-12 gap-2 px-4 py-3 border-b items-center hover:bg-muted/40 cursor-pointer transition-colors duration-200 group",
                  virtualRow.index % 2 === 0 ? "bg-background" : "bg-muted/5"
                )}
                onClick={() => onSelect(c)}
              >
                <div className="col-span-1 md:col-span-2 lg:col-span-3 font-semibold text-sm truncate group-hover:text-primary transition-colors">
                  {c.name}
                </div>
                <div className="hidden md:block md:col-span-1 lg:col-span-2 text-sm text-muted-foreground truncate">
                  {c.company}
                </div>
                <div className="hidden md:block md:col-span-1 lg:col-span-1 text-xs text-muted-foreground">
                  {c.industry}
                </div>
                <div className="col-span-1 md:col-span-1 lg:col-span-1 flex justify-center">
                  <Badge className={cn('text-[10px] font-bold px-1.5 py-0 h-4 uppercase', stage.color, stage.bg)}>
                    {stage.name}
                  </Badge>
                </div>
                <div className="hidden md:block md:col-span-1 lg:col-span-2 text-sm font-mono text-right font-medium">
                  {c.estimated_value > 0 ? `\u00A5${Number(c.estimated_value).toLocaleString()}` : '-'}
                </div>
                <div className="hidden lg:block lg:col-span-2 text-xs text-muted-foreground truncate">
                  {c.source || '-'}
                </div>
                <div className="col-span-1 md:col-span-1 lg:col-span-1 flex justify-end" onClick={e => e.stopPropagation()}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0 hover:bg-muted-foreground/10">
                        <MoreHorizontal className="w-4 h-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem onClick={() => onSelect(c)}>
                        <Eye className="w-4 h-4 mr-2" />
                        查看详情
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onEdit(c)}>
                        <Pencil className="w-4 h-4 mr-2" />
                        编辑
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem className="text-destructive focus:bg-destructive/10" onClick={() => onDelete(c)}>
                        <Trash2 className="w-4 h-4 mr-2" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

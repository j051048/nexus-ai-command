import React from 'react';
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
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 md:grid-cols-7 lg:grid-cols-12 gap-2 px-4 py-2 text-xs font-medium text-muted-foreground">
        <div className="col-span-1 md:col-span-2 lg:col-span-3">客户名称</div>
        <div className="hidden md:block md:col-span-1 lg:col-span-2">公司</div>
        <div className="hidden md:block md:col-span-1 lg:col-span-1">行业</div>
        <div className="col-span-1 md:col-span-1 lg:col-span-1">阶段</div>
        <div className="hidden md:block md:col-span-1 lg:col-span-2">预估金额</div>
        <div className="hidden lg:block lg:col-span-2">来源</div>
        <div className="col-span-1 md:col-span-1 lg:col-span-1">操作</div>
      </div>
      {customers.map(c => {
        const stage = STAGES[c.stage] || STAGES.lead;
        return (
          <div
            key={c.id}
            className="grid grid-cols-3 md:grid-cols-7 lg:grid-cols-12 gap-2 px-4 py-3 rounded-lg border items-center hover:bg-muted/50 cursor-pointer transition"
            onClick={() => onSelect(c)}
          >
            <div className="col-span-1 md:col-span-2 lg:col-span-3 font-medium truncate">{c.name}</div>
            <div className="hidden md:block md:col-span-1 lg:col-span-2 text-sm text-muted-foreground truncate">{c.company}</div>
            <div className="hidden md:block md:col-span-1 lg:col-span-1 text-sm text-muted-foreground">{c.industry}</div>
            <div className="col-span-1 md:col-span-1 lg:col-span-1">
              <Badge className={cn('text-xs', stage.color, stage.bg)}>{stage.name}</Badge>
            </div>
            <div className="hidden md:block md:col-span-1 lg:col-span-2 text-sm font-medium">
              {c.estimated_value > 0 ? `\u00A5${Number(c.estimated_value).toLocaleString()}` : '-'}
            </div>
            <div className="hidden lg:block lg:col-span-2 text-sm text-muted-foreground">{c.source || '-'}</div>
            <div className="col-span-1 md:col-span-1 lg:col-span-1" onClick={e => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                    <MoreHorizontal className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => onSelect(c)}>
                    <Eye className="w-4 h-4 mr-2" />
                    查看详情
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onEdit(c)}>
                    <Pencil className="w-4 h-4 mr-2" />
                    编辑
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem className="text-destructive" onClick={() => onDelete(c)}>
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
  );
}

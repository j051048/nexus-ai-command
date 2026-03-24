import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Search,
  LayoutGrid,
  List,
  RotateCcw,
} from 'lucide-react';
import { DataExport } from '@/components/common/DataExport';
import type { ExportColumn } from '@/components/common/DataExport';
import { STAGES, CRM_EXPORT_COLUMNS } from './constants';

export interface CustomerFiltersProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  stageFilter: string;
  onStageFilterChange: (value: string) => void;
  viewMode: 'kanban' | 'list';
  onViewModeChange: (mode: 'kanban' | 'list') => void;
  customers: Record<string, unknown>[];
  onReset?: () => void;
}

export default function CustomerFilters({
  searchQuery,
  onSearchChange,
  stageFilter,
  onStageFilterChange,
  viewMode,
  onViewModeChange,
  customers,
  onReset,
}: CustomerFiltersProps) {
  const isFiltered = searchQuery || stageFilter !== 'all';

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          className="pl-10 pr-16"
          placeholder="搜索客户名称或公司..."
          value={searchQuery}
          onChange={e => onSearchChange(e.target.value)}
        />
        {isFiltered && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
            <span className="text-[10px] font-medium bg-muted px-1.5 py-0.5 rounded text-muted-foreground uppercase tracking-tight">
              {customers.length} 结果
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Select value={stageFilter} onValueChange={onStageFilterChange}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="全部阶段" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部阶段</SelectItem>
            {Object.entries(STAGES).map(([key, val]) => (
              <SelectItem key={key} value={key}>{val.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-0 border rounded-md overflow-hidden bg-background shrink-0">
          <Button
            variant={viewMode === 'kanban' ? 'secondary' : 'ghost'}
            size="sm"
            className="h-8 px-3 rounded-none border-0"
            onClick={() => onViewModeChange('kanban')}
          >
            <LayoutGrid className="w-3.5 h-3.5 mr-1.5" />
            看板
          </Button>
          <div className="w-[1px] h-4 bg-border" />
          <Button
            variant={viewMode === 'list' ? 'secondary' : 'ghost'}
            size="sm"
            className="h-8 px-3 rounded-none border-0"
            onClick={() => onViewModeChange('list')}
          >
            <List className="w-3.5 h-3.5 mr-1.5" />
            列表
          </Button>
        </div>

        {isFiltered && onReset && (
          <Button variant="ghost" size="sm" onClick={onReset} className="h-8 text-xs gap-1.5 text-muted-foreground hover:text-foreground">
            <RotateCcw className="w-3.5 h-3.5" />
            重置
          </Button>
        )}
      </div>

      <div className="ml-auto">
        <DataExport
          data={customers}
          columns={CRM_EXPORT_COLUMNS}
          filename="crm_customers"
          title="导出客户数据"
          description="选择导出格式和列配置"
        />
      </div>
    </div>
  );
}

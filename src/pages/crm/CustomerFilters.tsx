import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Search,
  LayoutGrid,
  List,
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
}

export default function CustomerFilters({
  searchQuery,
  onSearchChange,
  stageFilter,
  onStageFilterChange,
  viewMode,
  onViewModeChange,
  customers,
}: CustomerFiltersProps) {
  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          className="pl-10"
          placeholder="搜索客户名称或公司..."
          value={searchQuery}
          onChange={e => onSearchChange(e.target.value)}
        />
      </div>
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
      <div className="flex items-center gap-1 border rounded-md">
        <Button
          variant={viewMode === 'kanban' ? 'default' : 'ghost'}
          size="sm"
          className="gap-1 rounded-r-none"
          onClick={() => onViewModeChange('kanban')}
        >
          <LayoutGrid className="w-4 h-4" />
          看板
        </Button>
        <Button
          variant={viewMode === 'list' ? 'default' : 'ghost'}
          size="sm"
          className="gap-1 rounded-l-none"
          onClick={() => onViewModeChange('list')}
        >
          <List className="w-4 h-4" />
          列表
        </Button>
      </div>
      <DataExport
        data={customers}
        columns={CRM_EXPORT_COLUMNS}
        filename="crm_customers"
        title="导出客户数据"
        description="选择导出格式和列配置"
      />
    </div>
  );
}

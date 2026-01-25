import React, { useState } from 'react';
import { format, subDays, startOfMonth, endOfMonth } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { Calendar as CalendarIcon, Download, Search, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useSalesMetricsByRange, exportToCSV, SalesMetric } from '@/hooks/useSalesData';
import { Skeleton } from '@/components/ui/skeleton';

export function SalesHistoryPanel() {
  const [startDate, setStartDate] = useState<Date | undefined>(
    startOfMonth(new Date())
  );
  const [endDate, setEndDate] = useState<Date | undefined>(
    endOfMonth(new Date())
  );

  const { data, isLoading, error } = useSalesMetricsByRange(
    startDate ? format(startDate, 'yyyy-MM-dd') : null,
    endDate ? format(endDate, 'yyyy-MM-dd') : null
  );

  const handleExport = () => {
    if (data && data.length > 0) {
      exportToCSV(data, 'sales-report');
    }
  };

  // Quick date range presets
  const setPresetRange = (preset: 'today' | 'week' | 'month' | 'quarter') => {
    const today = new Date();
    switch (preset) {
      case 'today':
        setStartDate(today);
        setEndDate(today);
        break;
      case 'week':
        setStartDate(subDays(today, 7));
        setEndDate(today);
        break;
      case 'month':
        setStartDate(startOfMonth(today));
        setEndDate(endOfMonth(today));
        break;
      case 'quarter':
        setStartDate(subDays(today, 90));
        setEndDate(today);
        break;
    }
  };

  // Calculate summary stats
  const summary = React.useMemo(() => {
    if (!data || data.length === 0) return null;
    
    return {
      totalLeads: data.reduce((sum, d) => sum + (d.leads_count || 0), 0),
      totalConversions: data.reduce((sum, d) => sum + (d.conversions || 0), 0),
      totalRevenue: data.reduce((sum, d) => sum + (Number(d.revenue) || 0), 0),
      avgWinRate: Math.round(
        data.reduce((sum, d) => sum + (Number(d.win_rate) || 0), 0) / data.length
      ),
      totalCalls: data.reduce((sum, d) => sum + (d.calls_made || 0), 0),
      avgScore: Math.round(
        data.reduce((sum, d) => sum + (d.score || 0), 0) / data.length
      ),
    };
  }, [data]);

  return (
    <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground">历史数据查询</h2>
          <p className="text-sm text-muted-foreground">按日期范围筛选销售数据</p>
        </div>
        
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPresetRange('today')}
          >
            今日
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPresetRange('week')}
          >
            近7天
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPresetRange('month')}
          >
            本月
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPresetRange('quarter')}
          >
            近3月
          </Button>
        </div>
      </div>

      {/* Date Range Pickers */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground whitespace-nowrap">开始日期:</span>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  "w-[180px] justify-start text-left font-normal",
                  !startDate && "text-muted-foreground"
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {startDate ? format(startDate, "yyyy-MM-dd") : "选择日期"}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="single"
                selected={startDate}
                onSelect={setStartDate}
                initialFocus
              />
            </PopoverContent>
          </Popover>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground whitespace-nowrap">结束日期:</span>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  "w-[180px] justify-start text-left font-normal",
                  !endDate && "text-muted-foreground"
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {endDate ? format(endDate, "yyyy-MM-dd") : "选择日期"}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="single"
                selected={endDate}
                onSelect={setEndDate}
                initialFocus
              />
            </PopoverContent>
          </Popover>
        </div>

        <Button 
          onClick={handleExport} 
          disabled={!data || data.length === 0}
          className="flex items-center gap-2"
        >
          <Download className="w-4 h-4" />
          导出CSV
        </Button>
      </div>

      {/* Summary Stats */}
      {summary && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
          <div className="bg-secondary/50 rounded-lg p-3 text-center">
            <p className="text-xs text-muted-foreground">总线索</p>
            <p className="text-lg font-bold text-foreground mono-number">{summary.totalLeads}</p>
          </div>
          <div className="bg-secondary/50 rounded-lg p-3 text-center">
            <p className="text-xs text-muted-foreground">总转化</p>
            <p className="text-lg font-bold text-success mono-number">{summary.totalConversions}</p>
          </div>
          <div className="bg-secondary/50 rounded-lg p-3 text-center">
            <p className="text-xs text-muted-foreground">总营收</p>
            <p className="text-lg font-bold text-foreground mono-number">¥{(summary.totalRevenue / 10000).toFixed(1)}万</p>
          </div>
          <div className="bg-secondary/50 rounded-lg p-3 text-center">
            <p className="text-xs text-muted-foreground">平均赢率</p>
            <p className="text-lg font-bold text-primary mono-number">{summary.avgWinRate}%</p>
          </div>
          <div className="bg-secondary/50 rounded-lg p-3 text-center">
            <p className="text-xs text-muted-foreground">总通话</p>
            <p className="text-lg font-bold text-foreground mono-number">{summary.totalCalls}</p>
          </div>
          <div className="bg-secondary/50 rounded-lg p-3 text-center">
            <p className="text-xs text-muted-foreground">平均绩效</p>
            <p className="text-lg font-bold text-foreground mono-number">{summary.avgScore}</p>
          </div>
        </div>
      )}

      {/* Data Table */}
      <div className="border rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="p-4 space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : error ? (
          <div className="p-8 text-center text-destructive">
            加载失败: {(error as Error).message}
          </div>
        ) : !data || data.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <Search className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>所选日期范围内暂无数据</p>
            <p className="text-sm mt-1">请选择其他日期范围或录入新数据</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>日期</TableHead>
                  <TableHead className="text-right">线索数</TableHead>
                  <TableHead className="text-right">转化数</TableHead>
                  <TableHead className="text-right">营收</TableHead>
                  <TableHead className="text-right">赢率</TableHead>
                  <TableHead className="text-right">通话数</TableHead>
                  <TableHead className="text-right">绩效分</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.date}</TableCell>
                    <TableCell className="text-right mono-number">{row.leads_count || 0}</TableCell>
                    <TableCell className="text-right mono-number text-success">{row.conversions || 0}</TableCell>
                    <TableCell className="text-right mono-number">¥{(Number(row.revenue) || 0).toLocaleString()}</TableCell>
                    <TableCell className="text-right mono-number">{row.win_rate || 0}%</TableCell>
                    <TableCell className="text-right mono-number">{row.calls_made || 0}</TableCell>
                    <TableCell className="text-right">
                      <span className={cn(
                        "px-2 py-0.5 rounded-full text-xs font-medium mono-number",
                        (row.score || 0) >= 90 && "bg-success/20 text-success",
                        (row.score || 0) >= 80 && (row.score || 0) < 90 && "bg-primary/20 text-primary",
                        (row.score || 0) < 80 && "bg-warning/20 text-warning"
                      )}>
                        {row.score || 0}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {data && data.length > 0 && (
        <p className="text-xs text-muted-foreground text-center">
          共 {data.length} 条记录
        </p>
      )}
    </div>
  );
}

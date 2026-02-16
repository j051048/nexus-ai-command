import React, { useState, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Shield,
  Activity,
  AlertTriangle,
  XCircle,
  Download,
  Search,
  Clock,
  User,
  Filter,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  FileText,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { format } from 'date-fns';
import { toast } from 'sonner';
import {
  useAuditLogs,
  useAuditStats,
  useAuditActions,
  type AuditFilters,
  type AuditLogEntry,
} from '@/hooks/useAuditLogs';

// ─── 状态图标与颜色 ──────────────────────────────────────────

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; label: string; color: string; bg: string }> = {
  success: {
    icon: <CheckCircle2 className="w-4 h-4" />,
    label: '成功',
    color: 'text-green-600',
    bg: 'bg-green-500/10',
  },
  failure: {
    icon: <XCircle className="w-4 h-4" />,
    label: '失败',
    color: 'text-red-600',
    bg: 'bg-red-500/10',
  },
  warning: {
    icon: <AlertCircle className="w-4 h-4" />,
    label: '告警',
    color: 'text-yellow-600',
    bg: 'bg-yellow-500/10',
  },
};

// ─── CSV 导出 ──────────────────────────────────────────────

function exportToCSV(logs: AuditLogEntry[]) {
  const headers = ['时间', '操作', '操作人', '目标', '状态', 'IP地址', '详情'];
  const rows = logs.map((log) => [
    format(new Date(log.created_at), 'yyyy-MM-dd HH:mm:ss'),
    log.action,
    log.actor,
    log.target || '',
    log.status,
    log.ip_address || '',
    log.details || '',
  ]);

  const csvContent = [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');

  const BOM = '\uFEFF';
  const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `audit-report-${format(new Date(), 'yyyyMMdd-HHmmss')}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// ─── 统计卡片组件 ──────────────────────────────────────────

function StatCard({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className={`p-3 rounded-lg ${color}`}>{icon}</div>
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── 时间线项 ──────────────────────────────────────────────

function TimelineItem({ log, isExpanded, onToggle }: { log: AuditLogEntry; isExpanded: boolean; onToggle: () => void }) {
  const statusCfg = STATUS_CONFIG[log.status] || STATUS_CONFIG.success;

  return (
    <div className="relative pl-8 pb-6 group">
      {/* 时间线点 */}
      <div
        className={`absolute left-0 top-1 w-6 h-6 rounded-full flex items-center justify-center ${statusCfg.bg} ${statusCfg.color} ring-2 ring-background`}
      >
        {statusCfg.icon}
      </div>
      {/* 连接线 */}
      <div className="absolute left-[11px] top-7 bottom-0 w-px bg-border group-last:hidden" />

      <div className="space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium">{log.action}</span>
          <Badge variant="outline" className={`text-xs ${statusCfg.color}`}>
            {statusCfg.label}
          </Badge>
          <span className="text-xs text-muted-foreground ml-auto">
            {format(new Date(log.created_at), 'MM-dd HH:mm:ss')}
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <User className="w-3 h-3" />
            {log.actor}
          </span>
          {log.target && (
            <span className="flex items-center gap-1">
              <FileText className="w-3 h-3" />
              {log.target}
            </span>
          )}
          {log.ip_address && (
            <span className="flex items-center gap-1">
              <Activity className="w-3 h-3" />
              {log.ip_address}
            </span>
          )}
        </div>

        {/* 展开详情 */}
        <button
          onClick={onToggle}
          className="flex items-center gap-1 text-xs text-primary hover:underline"
        >
          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {isExpanded ? '收起' : '详情'}
        </button>

        {isExpanded && log.details && (
          <div className="mt-1 p-2 rounded bg-muted/50 text-xs text-muted-foreground">
            {log.details}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── 主组件 ──────────────────────────────────────────────────

function AuditPanel() {
  // 筛选状态
  const [filters, setFilters] = useState<AuditFilters>({});
  const [searchActor, setSearchActor] = useState('');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(true);

  // 数据
  const { data: logs = [], isLoading: logsLoading, refetch } = useAuditLogs(filters);
  const { data: stats } = useAuditStats(filters);
  const { data: actions = [] } = useAuditActions();

  // 操作频率图表数据
  const hourlyData = useMemo(() => {
    return (stats?.hourlyDistribution || []).map((d) => ({
      name: `${String(d.hour).padStart(2, '0')}:00`,
      count: d.count,
    }));
  }, [stats]);

  // 展开/收起
  const toggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // 应用搜索
  const handleSearch = useCallback(() => {
    setFilters((prev) => ({ ...prev, actor: searchActor || undefined }));
  }, [searchActor]);

  // 重置筛选
  const handleResetFilters = useCallback(() => {
    setFilters({});
    setSearchActor('');
  }, []);

  // 导出
  const handleExport = useCallback(() => {
    if (logs.length === 0) {
      toast.error('暂无数据可导出');
      return;
    }
    exportToCSV(logs);
    toast.success(`已导出 ${logs.length} 条审计记录`);
  }, [logs]);

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* 页面标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Shield className="w-7 h-7 text-primary" />
            操作审计面板
          </h1>
          <p className="text-sm text-muted-foreground">
            查看系统操作记录，追踪安全事件
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-1" />
            刷新
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="w-4 h-4 mr-1" />
            导出 CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="w-4 h-4 mr-1" />
            {showFilters ? '收起筛选' : '展开筛选'}
          </Button>
        </div>
      </div>

      {/* 筛选栏 */}
      {showFilters && (
        <Card>
          <CardContent className="p-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-end">
              {/* 开始时间 */}
              <div className="space-y-1">
                <Label className="text-xs">开始日期</Label>
                <Input
                  type="date"
                  value={filters.startDate || ''}
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, startDate: e.target.value || undefined }))
                  }
                  className="h-9 text-sm"
                />
              </div>

              {/* 结束时间 */}
              <div className="space-y-1">
                <Label className="text-xs">结束日期</Label>
                <Input
                  type="date"
                  value={filters.endDate || ''}
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, endDate: e.target.value || undefined }))
                  }
                  className="h-9 text-sm"
                />
              </div>

              {/* 操作类型 */}
              <div className="space-y-1">
                <Label className="text-xs">操作类型</Label>
                <Select
                  value={filters.action || 'all'}
                  onValueChange={(val) =>
                    setFilters((prev) => ({ ...prev, action: val === 'all' ? undefined : val }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="全部" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部</SelectItem>
                    {actions.map((a) => (
                      <SelectItem key={a} value={a}>
                        {a}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* 状态 */}
              <div className="space-y-1">
                <Label className="text-xs">状态</Label>
                <Select
                  value={filters.status || 'all'}
                  onValueChange={(val) =>
                    setFilters((prev) => ({ ...prev, status: val === 'all' ? undefined : val }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="全部" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部</SelectItem>
                    <SelectItem value="success">成功</SelectItem>
                    <SelectItem value="failure">失败</SelectItem>
                    <SelectItem value="warning">告警</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* 操作人搜索 */}
              <div className="space-y-1">
                <Label className="text-xs">操作人</Label>
                <div className="flex gap-1">
                  <Input
                    value={searchActor}
                    onChange={(e) => setSearchActor(e.target.value)}
                    placeholder="搜索操作人"
                    className="h-9 text-sm"
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  />
                  <Button size="sm" variant="secondary" className="h-9 px-2" onClick={handleSearch}>
                    <Search className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex justify-end mt-3">
              <Button variant="ghost" size="sm" onClick={handleResetFilters}>
                重置筛选
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="总操作数"
          value={stats?.totalOps ?? 0}
          icon={<Activity className="w-5 h-5 text-blue-600" />}
          color="bg-blue-500/10"
        />
        <StatCard
          title="失败操作"
          value={stats?.failedOps ?? 0}
          icon={<XCircle className="w-5 h-5 text-red-600" />}
          color="bg-red-500/10"
        />
        <StatCard
          title="安全告警"
          value={stats?.securityAlerts ?? 0}
          icon={<AlertTriangle className="w-5 h-5 text-yellow-600" />}
          color="bg-yellow-500/10"
        />
      </div>

      {/* 操作频率分布 */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Clock className="w-4 h-4 text-primary" />
            操作频率分布（按小时）
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={hourlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11 }}
                stroke="hsl(var(--muted-foreground))"
                interval={2}
              />
              <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
              <Tooltip
                contentStyle={{
                  background: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={(value: number) => [`${value} 次`, '操作次数']}
              />
              <Bar dataKey="count" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* 操作时间线 */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Clock className="w-4 h-4 text-primary" />
              操作时间线
            </CardTitle>
            <Badge variant="secondary" className="text-xs">
              {logs.length} 条记录
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {logsLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <RefreshCw className="w-5 h-5 animate-spin mr-2" />
              加载中...
            </div>
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Shield className="w-10 h-10 mb-3 opacity-40" />
              <p>暂无审计记录</p>
              <p className="text-xs mt-1">请调整筛选条件或等待新的操作产生</p>
            </div>
          ) : (
            <ScrollArea className="h-[500px] pr-4">
              <div className="space-y-0 pt-2">
                {logs.map((log) => (
                  <TimelineItem
                    key={log.id}
                    log={log}
                    isExpanded={expandedIds.has(log.id)}
                    onToggle={() => toggleExpand(log.id)}
                  />
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default AuditPanel;

import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { X, Settings, TrendingUp, TrendingDown } from 'lucide-react';
import type { DashboardCardConfig, CardType } from '@/hooks/useDashboardConfig';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';

import { CHART_COLORS } from '@/lib/chartColors';

// ─── Mock 数据 ──────────────────────────────────────────────

const COLORS = CHART_COLORS;

const BAR_DATA: { name: string; value: number }[] = [];

const PIE_DATA: { name: string; value: number }[] = [];

const LINE_DATA: { name: string; value: number; prev: number }[] = [];

const LEADERBOARD_DATA: { rank: number; name: string; value: string }[] = [];

const KPI_MAP: Record<string, { value: string; change: number; unit: string }> = {
  sales: { value: '—', change: 0, unit: '元' },
  approval: { value: '—', change: 0, unit: '件' },
  project: { value: '—', change: 0, unit: '个' },
  hr: { value: '—', change: 0, unit: '人' },
  finance: { value: '—', change: 0, unit: '元' },
  performance: { value: '—', change: 0, unit: '分' },
};

const APPROVAL_STATS = {
  total: 0,
  approved: 0,
  pending: 0,
  rejected: 0,
  withdrawn: 0,
};

// ─── 子渲染组件 ──────────────────────────────────────────────

function KPIContent({ dataSource }: { dataSource: string }) {
  const kpi = KPI_MAP[dataSource] || KPI_MAP.sales;
  const isPositive = kpi.change >= 0;

  return (
    <div className="flex flex-col gap-2">
      <p className="text-3xl font-bold tracking-tight">{kpi.value}</p>
      <div className="flex items-center gap-1 text-sm">
        {isPositive ? (
          <TrendingUp className="w-4 h-4 text-green-500" />
        ) : (
          <TrendingDown className="w-4 h-4 text-red-500" />
        )}
        <span className={isPositive ? 'text-green-500' : 'text-red-500'}>
          {isPositive ? '+' : ''}
          {kpi.change}%
        </span>
        <span className="text-muted-foreground">较上期</span>
      </div>
    </div>
  );
}

function BarChartContent() {
  if (BAR_DATA.length === 0) {
    return <div className="flex items-center justify-center h-full text-sm text-muted-foreground">暂无数据</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={BAR_DATA}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
        <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
        <Tooltip
          contentStyle={{
            background: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '8px',
          }}
        />
        <Bar dataKey="value" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function PieChartContent() {
  if (PIE_DATA.length === 0) {
    return <div className="flex items-center justify-center h-full text-sm text-muted-foreground">暂无数据</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={PIE_DATA}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={4}
          dataKey="value"
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
        >
          {PIE_DATA.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  );
}

function LineChartContent() {
  if (LINE_DATA.length === 0) {
    return <div className="flex items-center justify-center h-full text-sm text-muted-foreground">暂无数据</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={LINE_DATA}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
        <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
        <Tooltip
          contentStyle={{
            background: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '8px',
          }}
        />
        <Legend />
        <Line type="monotone" dataKey="value" stroke="hsl(var(--primary))" strokeWidth={2} name="本期" dot={false} />
        <Line type="monotone" dataKey="prev" stroke="hsl(var(--primary) / 0.5)" strokeWidth={2} strokeDasharray="5 5" name="上期" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function ApprovalStatsContent() {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="text-center p-3 rounded-lg bg-muted/50">
        <p className="text-2xl font-bold">{APPROVAL_STATS.total}</p>
        <p className="text-xs text-muted-foreground">总数</p>
      </div>
      <div className="text-center p-3 rounded-lg bg-green-500/10">
        <p className="text-2xl font-bold text-green-600">{APPROVAL_STATS.approved}</p>
        <p className="text-xs text-muted-foreground">已通过</p>
      </div>
      <div className="text-center p-3 rounded-lg bg-yellow-500/10">
        <p className="text-2xl font-bold text-yellow-600">{APPROVAL_STATS.pending}</p>
        <p className="text-xs text-muted-foreground">待审批</p>
      </div>
      <div className="text-center p-3 rounded-lg bg-red-500/10">
        <p className="text-2xl font-bold text-red-600">{APPROVAL_STATS.rejected}</p>
        <p className="text-xs text-muted-foreground">已拒绝</p>
      </div>
    </div>
  );
}

function LeaderboardContent() {
  if (LEADERBOARD_DATA.length === 0) {
    return <div className="flex items-center justify-center h-full text-sm text-muted-foreground">暂无数据</div>;
  }

  return (
    <div className="space-y-2">
      {LEADERBOARD_DATA.map((item) => (
        <div key={item.rank} className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors">
          <Badge
            variant={item.rank <= 3 ? 'default' : 'secondary'}
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs shrink-0"
          >
            {item.rank}
          </Badge>
          <span className="flex-1 text-sm font-medium">{item.name}</span>
          <span className="text-sm font-mono text-muted-foreground">{item.value}</span>
        </div>
      ))}
    </div>
  );
}

// ─── 内容分发 ──────────────────────────────────────────────

function CardTypeContent({ type, dataSource }: { type: CardType; dataSource: string }) {
  switch (type) {
    case 'kpi':
      return <KPIContent dataSource={dataSource} />;
    case 'bar':
      return <BarChartContent />;
    case 'pie':
      return <PieChartContent />;
    case 'line':
      return <LineChartContent />;
    case 'approval_stats':
      return <ApprovalStatsContent />;
    case 'leaderboard':
      return <LeaderboardContent />;
    default:
      return <p className="text-sm text-muted-foreground">未知类型</p>;
  }
}

// ─── 主组件 ──────────────────────────────────────────────────

interface DashboardCardProps {
  config: DashboardCardConfig;
  isEditing: boolean;
  onRemove: (id: string) => void;
  onEdit: (id: string) => void;
}

export function DashboardCard({ config, isEditing, onRemove, onEdit }: DashboardCardProps) {
  return (
    <Card
      className={`relative transition-all ${
        isEditing ? 'ring-2 ring-dashed ring-primary/30 hover:ring-primary/50' : 'hover:shadow-md'
      } ${config.colSpan === 2 ? 'md:col-span-2' : ''}`}
    >
      {isEditing && (
        <div className="absolute top-2 right-2 flex items-center gap-1 z-10">
          <Button variant="ghost" size="icon" className="h-7 w-7" data-compact onClick={() => onEdit(config.id)}>
            <Settings className="w-3.5 h-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" data-compact onClick={() => onRemove(config.id)}>
            <X className="w-3.5 h-3.5" />
          </Button>
        </div>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{config.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <CardTypeContent type={config.type} dataSource={config.dataSource} />
      </CardContent>
    </Card>
  );
}

export default DashboardCard;

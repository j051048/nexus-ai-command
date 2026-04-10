import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import {
  FileText,
  Play,
  Save,
  Clock,
  Loader2,
  Trash2,
  Eye,
  BarChart3,
  Table2,
  Sparkles,
} from 'lucide-react';
import { httpClient } from '@/lib/httpClient';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

interface ApiResponse<T> {
  status: number;
  message?: string;
  data: T;
}

interface ChartConfig {
  type: string;
  x_key?: string;
  y_keys?: string[];
}

interface SavedReport {
  id: string;
  title: string;
  nl_query: string;
  summary?: string;
  is_public: boolean;
  created_at: string;
}

interface Schedule {
  id: string;
  name: string;
  nl_query: string;
  schedule_type: string;
  hour: number;
  day_of_week?: number;
  day_of_month?: number;
  is_active: boolean;
  next_execution_at?: string;
  last_executed_at?: string;
  failure_count: number;
  recipients: { type: string; value: string }[];
  output_format: string;
}

const CHART_COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4'];

function ReportBuilderPage() {
  // Generation state
  const [nlQuery, setNlQuery] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generatedSql, setGeneratedSql] = useState('');
  const [resultData, setResultData] = useState<Record<string, unknown>[]>([]);
  const [chartConfig, setChartConfig] = useState<ChartConfig>({ type: 'table' });
  const [summary, setSummary] = useState('');

  // Save state
  const [reportTitle, setReportTitle] = useState('');
  const [saving, setSaving] = useState(false);

  // Saved reports
  const [savedReports, setSavedReports] = useState<SavedReport[]>([]);
  const [loadingSaved, setLoadingSaved] = useState(false);

  // Schedule state
  const [schedName, setSchedName] = useState('');
  const [schedType, setSchedType] = useState('daily');
  const [schedHour, setSchedHour] = useState(9);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [creatingSched, setCreatingSched] = useState(false);

  // Active tab
  const [activeTab, setActiveTab] = useState<'build' | 'saved' | 'schedules'>('build');

  // Load saved reports and schedules
  const loadData = useCallback(async () => {
    setLoadingSaved(true);
    try {
      const [reportsRes, schedsRes] = await Promise.all([
        httpClient.get<ApiResponse<SavedReport[]>>('/api/report-engine/saved'),
        httpClient.get<ApiResponse<Schedule[]>>('/api/report-engine/schedules'),
      ]);
      setSavedReports(reportsRes.data?.data || []);
      setSchedules(schedsRes.data?.data || []);
    } catch {
      // ignore
    } finally {
      setLoadingSaved(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Generate report
  const handleGenerate = async () => {
    if (!nlQuery.trim()) return;
    setGenerating(true);
    try {
      const res = await httpClient.post<ApiResponse<{
        sql: string; result: Record<string, unknown>[];
        total_rows: number; chart_config: ChartConfig; summary: string;
      }>>('/api/report-engine/generate', { nl_query: nlQuery.trim() });

      const d = res.data.data;
      setGeneratedSql(d.sql);
      setResultData(d.result);
      setChartConfig(d.chart_config);
      setSummary(d.summary);
      if (!reportTitle) setReportTitle(nlQuery.trim().slice(0, 30));
      toast.success(`报表已生成，${d.total_rows} 行数据`);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } }, message?: string };
      toast.error(`生成失败: ${e.response?.data?.message || e.message || '未知错误'}`);
    } finally {
      setGenerating(false);
    }
  };

  // Save report
  const handleSave = async () => {
    if (!reportTitle.trim() || !generatedSql) return;
    setSaving(true);
    try {
      await httpClient.post('/api/report-engine/save', {
        title: reportTitle.trim(),
        nl_query: nlQuery.trim(),
        generated_sql: generatedSql,
        result_data: resultData,
        chart_config: chartConfig,
        summary,
        is_public: false,
      });
      toast.success('报表已保存');
      loadData();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } }, message?: string };
      toast.error(`保存失败: ${e.response?.data?.message || e.message || '未知错误'}`);
    } finally {
      setSaving(false);
    }
  };

  // Create schedule
  const handleCreateSchedule = async () => {
    if (!schedName.trim() || !nlQuery.trim()) return;
    setCreatingSched(true);
    try {
      await httpClient.post('/api/report-engine/schedules', {
        name: schedName.trim(),
        nl_query: nlQuery.trim(),
        schedule_type: schedType,
        hour: schedHour,
      });
      toast.success('定时报表已创建');
      setSchedName('');
      loadData();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } }, message?: string };
      toast.error(`创建失败: ${e.response?.data?.message || e.message || '未知错误'}`);
    } finally {
      setCreatingSched(false);
    }
  };

  // Delete schedule
  const handleDeleteSchedule = async (id: string) => {
    try {
      await httpClient.delete(`/api/report-engine/schedules/${id}`);
      toast.success('定时报表已删除');
      loadData();
    } catch { toast.error('删除失败'); }
  };

  // Toggle schedule
  const handleToggleSchedule = async (id: string, active: boolean) => {
    try {
      await httpClient.put(`/api/report-engine/schedules/${id}/toggle`, null, { params: { active } });
      loadData();
    } catch { toast.error('操作失败'); }
  };

  // Render chart
  const renderChart = () => {
    if (!resultData.length || chartConfig.type === 'table' || chartConfig.type === 'none') {
      return renderTable();
    }

    const { type, x_key, y_keys } = chartConfig;
    if (!x_key || !y_keys?.length) return renderTable();

    if (type === 'bar') {
      return (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={resultData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={x_key} />
            <YAxis />
            <Tooltip />
            <Legend />
            {y_keys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      );
    }

    if (type === 'line') {
      return (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={resultData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={x_key} />
            <YAxis />
            <Tooltip />
            <Legend />
            {y_keys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      );
    }

    if (type === 'pie' && y_keys[0]) {
      return (
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie data={resultData} dataKey={y_keys[0]} nameKey={x_key} cx="50%" cy="50%" outerRadius={100} label>
              {resultData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      );
    }

    return renderTable();
  };

  // Render data table
  const renderTable = () => {
    if (!resultData.length) return <p className="text-sm text-muted-foreground">暂无数据</p>;
    const cols = Object.keys(resultData[0]);
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              {cols.map((c) => <th key={c} className="text-left py-2 px-3 font-medium text-muted-foreground">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {resultData.slice(0, 50).map((row, i) => (
              <tr key={i} className="border-b hover:bg-muted/30">
                {cols.map((c) => <td key={c} className="py-2 px-3">{String(row[c] ?? '')}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {resultData.length > 50 && <p className="text-xs text-muted-foreground mt-2">显示前 50 行，共 {resultData.length} 行</p>}
      </div>
    );
  };

  const tabs = [
    { key: 'build' as const, label: '构建报表', icon: <Sparkles className="w-4 h-4" /> },
    { key: 'saved' as const, label: '已保存', icon: <FileText className="w-4 h-4" /> },
    { key: 'schedules' as const, label: '定时报表', icon: <Clock className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <BarChart3 className="w-7 h-7 text-primary" />
          AI 报表引擎
        </h1>
        <p className="text-sm text-muted-foreground">用自然语言生成数据报表，支持定时推送</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {tabs.map((tab) => (
          <Button
            key={tab.key}
            variant={activeTab === tab.key ? 'default' : 'outline'}
            size="sm"
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.icon}
            <span className="ml-1.5">{tab.label}</span>
          </Button>
        ))}
      </div>

      {/* Build Tab */}
      {activeTab === 'build' && (
        <div className="space-y-4">
          {/* NL Query Input */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">自然语言查询</CardTitle>
              <CardDescription>描述你想查看的数据，AI 将自动生成 SQL 并执行</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                value={nlQuery}
                onChange={(e) => setNlQuery(e.target.value)}
                placeholder="例如：上个月各行业的客户数量和总估值"
                rows={3}
                className="resize-none"
              />
              <Button onClick={handleGenerate} disabled={generating || !nlQuery.trim()}>
                {generating ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Play className="w-4 h-4 mr-1" />}
                生成报表
              </Button>
            </CardContent>
          </Card>

          {/* Results */}
          {generatedSql && (
            <>
              {/* SQL Preview */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Eye className="w-4 h-4" /> 生成的 SQL
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs bg-muted/50 rounded-lg p-4 overflow-x-auto font-mono">{generatedSql}</pre>
                </CardContent>
              </Card>

              {/* Chart / Table */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    {chartConfig.type === 'table' ? <Table2 className="w-4 h-4" /> : <BarChart3 className="w-4 h-4" />}
                    数据结果
                    <Badge variant="secondary" className="ml-2">{resultData.length} 行</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {renderChart()}
                </CardContent>
              </Card>

              {/* AI Summary */}
              {summary && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Sparkles className="w-4 h-4" /> AI 洞察
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-relaxed">{summary}</p>
                  </CardContent>
                </Card>
              )}

              {/* Save & Schedule */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">保存报表</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Input
                      value={reportTitle}
                      onChange={(e) => setReportTitle(e.target.value)}
                      placeholder="报表标题"
                    />
                    <Button onClick={handleSave} disabled={saving || !reportTitle.trim()} size="sm" className="w-full">
                      {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Save className="w-4 h-4 mr-1" />}
                      保存
                    </Button>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">设为定时报表</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Input
                      value={schedName}
                      onChange={(e) => setSchedName(e.target.value)}
                      placeholder="定时任务名称"
                    />
                    <div className="flex gap-2">
                      <Select value={schedType} onValueChange={setSchedType}>
                        <SelectTrigger className="flex-1"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="daily">每天</SelectItem>
                          <SelectItem value="weekly">每周</SelectItem>
                          <SelectItem value="monthly">每月</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        type="number"
                        value={schedHour}
                        onChange={(e) => setSchedHour(Number(e.target.value))}
                        min={0} max={23}
                        className="w-20"
                        placeholder="时"
                      />
                      <span className="text-sm text-muted-foreground self-center">:00</span>
                    </div>
                    <Button onClick={handleCreateSchedule} disabled={creatingSched || !schedName.trim()} size="sm" className="w-full">
                      {creatingSched ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Clock className="w-4 h-4 mr-1" />}
                      创建定时
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </div>
      )}

      {/* Saved Reports Tab */}
      {activeTab === 'saved' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">已保存的报表</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingSaved ? (
              <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
            ) : savedReports.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">暂无保存的报表</p>
            ) : (
              <div className="space-y-2">
                {savedReports.map((r) => (
                  <div key={r.id} className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/30">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{r.title}</p>
                      <p className="text-xs text-muted-foreground truncate">{r.nl_query}</p>
                      {r.summary && <p className="text-xs text-muted-foreground mt-1 truncate">{r.summary}</p>}
                    </div>
                    <div className="flex items-center gap-2 ml-3">
                      {r.is_public && <Badge variant="secondary" className="text-xs">公开</Badge>}
                      <span className="text-xs text-muted-foreground">{new Date(r.created_at).toLocaleDateString('zh-CN')}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Schedules Tab */}
      {activeTab === 'schedules' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">定时报表</CardTitle>
          </CardHeader>
          <CardContent>
            {schedules.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">暂无定时报表</p>
            ) : (
              <div className="space-y-2">
                {schedules.map((s) => (
                  <div key={s.id} className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/30">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">{s.name}</p>
                      <p className="text-xs text-muted-foreground truncate">{s.nl_query}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">
                          {s.schedule_type === 'daily' ? '每天' : s.schedule_type === 'weekly' ? '每周' : '每月'} {s.hour}:00
                        </Badge>
                        {s.next_execution_at && (
                          <span className="text-xs text-muted-foreground">
                            下次: {new Date(s.next_execution_at).toLocaleString('zh-CN')}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-3">
                      <Switch
                        checked={s.is_active}
                        onCheckedChange={(v) => handleToggleSchedule(s.id, v)}
                      />
                      <Button variant="ghost" size="sm" onClick={() => handleDeleteSchedule(s.id)}>
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default ReportBuilderPage;

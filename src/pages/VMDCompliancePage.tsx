/**
 * VMD 合规校验页面
 * 内容输入 + 类别复选框 + LLM深度分析开关 + 校验结果面板 + 历史记录
 */

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import {
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Loader2,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  Search,
  Clock,
  FileText,
  Sparkles,
} from 'lucide-react';
import {
  useComplianceCheck,
  useComplianceLogs,
  type ComplianceResult,
} from '@/hooks/useVMD';
import { toast } from 'sonner';

// ---------- 配置 ----------

const CATEGORIES = [
  { value: 'advertising_law', label: '广告法', description: '《中华人民共和国广告法》合规审查' },
  { value: 'metrology_law', label: '计量法', description: '《中华人民共和国计量法》规范检查' },
  { value: 'bidding_law', label: '招投标法', description: '《招标投标法》及实施条例审查' },
  { value: 'medical_device', label: '医疗器械', description: '医疗器械广告与标签合规' },
  { value: 'industry_standard', label: '行业标准', description: '行业特定合规标准与规范' },
];

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ElementType }> = {
  error: {
    label: '严重',
    color: 'text-red-700 dark:text-red-300',
    bg: 'bg-red-100 dark:bg-red-900/50',
    icon: ShieldX,
  },
  warning: {
    label: '警告',
    color: 'text-amber-700 dark:text-amber-300',
    bg: 'bg-amber-100 dark:bg-amber-900/50',
    icon: AlertTriangle,
  },
  info: {
    label: '提示',
    color: 'text-blue-700 dark:text-blue-300',
    bg: 'bg-blue-100 dark:bg-blue-900/50',
    icon: Info,
  },
};

const CATEGORY_NAMES: Record<string, string> = Object.fromEntries(CATEGORIES.map(c => [c.value, c.label]));

// ---------- 组件 ----------

export default function VMDCompliancePage() {
  const [activeTab, setActiveTab] = useState('check');

  // Check form
  const [content, setContent] = useState('');
  const [selectedCategories, setSelectedCategories] = useState<string[]>(['advertising_law']);
  const [useLLM, setUseLLM] = useState(false);

  // Results
  const [results, setResults] = useState<ComplianceResult[] | null>(null);
  const [resultStatus, setResultStatus] = useState<'clean' | 'has_issues' | null>(null);

  // Queries & Mutations
  const complianceCheck = useComplianceCheck();
  const { data: logs, isLoading: logsLoading } = useComplianceLogs();

  const toggleCategory = (cat: string) => {
    setSelectedCategories(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );
  };

  const handleCheck = async () => {
    if (!content.trim()) {
      toast.error('请输入待校验的内容');
      return;
    }
    if (selectedCategories.length === 0) {
      toast.error('请至少选择一个校验类别');
      return;
    }

    try {
      const data = await complianceCheck.mutateAsync({
        content,
        categories: selectedCategories,
      });
      setResults(data);
      setResultStatus(data.length === 0 ? 'clean' : 'has_issues');
    } catch {
      setResults(null);
      setResultStatus(null);
    }
  };

  const handleClear = () => {
    setContent('');
    setResults(null);
    setResultStatus(null);
  };

  // Count issues by severity
  const severityCounts = (results || []).reduce((acc, r) => {
    acc[r.severity] = (acc[r.severity] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">合规校验</h1>
        <p className="text-muted-foreground">基于法律法规的智能内容合规检测</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="check" className="gap-1.5">
            <Search className="w-3.5 h-3.5" /> 内容校验
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-1.5">
            <Clock className="w-3.5 h-3.5" /> 历史记录
          </TabsTrigger>
        </TabsList>

        {/* ====== Check Tab ====== */}
        <TabsContent value="check" className="mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Left: Input */}
            <div className="lg:col-span-2 space-y-4">
              {/* Content Input */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    待校验内容
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Textarea
                    placeholder={'请粘贴或输入需要合规校验的文本内容。\n\n支持：广告文案、招标文件、产品说明书、宣传材料等...'}
                    rows={12}
                    className="resize-none"
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                  />
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{content.length} 字</span>
                  </div>
                </CardContent>
              </Card>

              {/* Category Selection */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">校验类别</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {CATEGORIES.map((cat) => {
                    const isSelected = selectedCategories.includes(cat.value);
                    return (
                      <div
                        key={cat.value}
                        className={cn(
                          "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                          isSelected
                            ? "border-primary/50 bg-primary/5"
                            : "border-border/50 hover:bg-muted/30"
                        )}
                        onClick={() => toggleCategory(cat.value)}
                      >
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => toggleCategory(cat.value)}
                          className="mt-0.5"
                        />
                        <div>
                          <p className="text-sm font-medium">{cat.label}</p>
                          <p className="text-xs text-muted-foreground">{cat.description}</p>
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>

              {/* LLM Toggle + Actions */}
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-amber-500" />
                      <div>
                        <Label className="text-sm font-medium">LLM 深度分析</Label>
                        <p className="text-xs text-muted-foreground">使用大语言模型进行语义级合规分析</p>
                      </div>
                    </div>
                    <Switch checked={useLLM} onCheckedChange={setUseLLM} />
                  </div>

                  <div className="flex gap-2">
                    <Button className="flex-1" onClick={handleCheck} disabled={complianceCheck.isPending}>
                      {complianceCheck.isPending ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <ShieldCheck className="w-4 h-4 mr-2" />
                      )}
                      开始校验
                    </Button>
                    <Button variant="outline" onClick={handleClear}>清空</Button>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right: Results */}
            <div className="lg:col-span-3 space-y-4">
              {complianceCheck.isPending ? (
                <Card>
                  <CardContent className="py-16 text-center">
                    <Loader2 className="w-10 h-10 text-primary mx-auto mb-4 animate-spin" />
                    <p className="text-muted-foreground">正在进行合规校验...</p>
                    {useLLM && (
                      <p className="text-xs text-muted-foreground mt-1">LLM 深度分析可能需要更长时间</p>
                    )}
                  </CardContent>
                </Card>
              ) : resultStatus === null ? (
                <Card>
                  <CardContent className="py-16 text-center">
                    <ShieldCheck className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                    <h3 className="text-lg font-medium">等待校验</h3>
                    <p className="text-muted-foreground">在左侧输入内容并选择校验类别后开始</p>
                  </CardContent>
                </Card>
              ) : (
                <>
                  {/* Result Banner */}
                  <Card className={cn(
                    "border-2",
                    resultStatus === 'clean'
                      ? "border-green-300 dark:border-green-700"
                      : "border-red-300 dark:border-red-700"
                  )}>
                    <CardContent className="py-6">
                      <div className="flex items-center gap-4">
                        {resultStatus === 'clean' ? (
                          <>
                            <div className="w-14 h-14 rounded-full bg-green-100 dark:bg-green-900/50 flex items-center justify-center">
                              <CheckCircle2 className="w-7 h-7 text-green-600 dark:text-green-400" />
                            </div>
                            <div>
                              <h3 className="text-lg font-semibold text-green-700 dark:text-green-300">
                                合规通过
                              </h3>
                              <p className="text-sm text-muted-foreground">
                                未检测到合规问题，内容符合所选校验类别的要求
                              </p>
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="w-14 h-14 rounded-full bg-red-100 dark:bg-red-900/50 flex items-center justify-center">
                              <ShieldAlert className="w-7 h-7 text-red-600 dark:text-red-400" />
                            </div>
                            <div className="flex-1">
                              <h3 className="text-lg font-semibold text-red-700 dark:text-red-300">
                                检测到合规问题
                              </h3>
                              <div className="flex items-center gap-3 mt-1">
                                <span className="text-sm text-muted-foreground">
                                  共 {results?.length || 0} 个问题
                                </span>
                                {severityCounts['error'] > 0 && (
                                  <Badge className="bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 text-[10px]">
                                    {severityCounts['error']} 严重
                                  </Badge>
                                )}
                                {severityCounts['warning'] > 0 && (
                                  <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300 text-[10px]">
                                    {severityCounts['warning']} 警告
                                  </Badge>
                                )}
                                {severityCounts['info'] > 0 && (
                                  <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 text-[10px]">
                                    {severityCounts['info']} 提示
                                  </Badge>
                                )}
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Issue List */}
                  {results && results.length > 0 && (
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-base">问题详情</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ScrollArea className="max-h-[500px]">
                          <div className="space-y-3">
                            {results.map((issue, idx) => {
                              const sevCfg = SEVERITY_CONFIG[issue.severity] || SEVERITY_CONFIG.info;
                              const SevIcon = sevCfg.icon;
                              return (
                                <div
                                  key={issue.id || idx}
                                  className={cn("rounded-lg border p-4", sevCfg.bg)}
                                >
                                  <div className="flex items-start gap-3">
                                    <SevIcon className={cn("w-5 h-5 mt-0.5 shrink-0", sevCfg.color)} />
                                    <div className="flex-1 min-w-0 space-y-2">
                                      {/* Header */}
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <Badge className={cn("text-[10px]", sevCfg.bg, sevCfg.color)}>
                                          {sevCfg.label}
                                        </Badge>
                                        <Badge variant="outline" className="text-[10px]">
                                          {CATEGORY_NAMES[issue.category] || issue.category}
                                        </Badge>
                                      </div>

                                      {/* Matched text (highlighted) */}
                                      {issue.matched_text && (
                                        <div className="bg-background/60 rounded-md p-2 border border-border/50">
                                          <p className="text-xs text-muted-foreground mb-1">匹配文本：</p>
                                          <p className="text-sm">
                                            <mark className="bg-red-200 dark:bg-red-800/60 px-0.5 rounded">
                                              {issue.matched_text}
                                            </mark>
                                          </p>
                                        </div>
                                      )}

                                      {/* Suggestion */}
                                      {issue.suggestion && (
                                        <div className="flex items-start gap-2">
                                          <AlertCircle className="w-3.5 h-3.5 mt-0.5 text-muted-foreground shrink-0" />
                                          <p className="text-sm text-muted-foreground">{issue.suggestion}</p>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </ScrollArea>
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </div>
          </div>
        </TabsContent>

        {/* ====== History Tab ====== */}
        <TabsContent value="history" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">校验历史</CardTitle>
            </CardHeader>
            <CardContent>
              {logsLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : !logs || logs.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Clock className="w-10 h-10 mx-auto mb-3 opacity-50" />
                  <p>暂无校验记录</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/30">
                        <th className="text-left p-3 text-xs font-medium text-muted-foreground">来源</th>
                        <th className="text-left p-3 text-xs font-medium text-muted-foreground">结果</th>
                        <th className="text-left p-3 text-xs font-medium text-muted-foreground">问题数</th>
                        <th className="text-left p-3 text-xs font-medium text-muted-foreground">校验时间</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logs.map((log) => (
                        <tr key={log.id} className="border-b last:border-b-0 hover:bg-muted/20 transition-colors">
                          <td className="p-3">
                            <span className="text-sm">{log.source || '手动输入'}</span>
                          </td>
                          <td className="p-3">
                            {log.status === 'clean' ? (
                              <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 text-xs gap-1">
                                <CheckCircle2 className="w-3 h-3" /> 合规
                              </Badge>
                            ) : (
                              <Badge className="bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 text-xs gap-1">
                                <ShieldAlert className="w-3 h-3" /> 有问题
                              </Badge>
                            )}
                          </td>
                          <td className="p-3 text-sm">{log.total_issues}</td>
                          <td className="p-3 text-xs text-muted-foreground">
                            {new Date(log.created_at).toLocaleString('zh-CN')}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

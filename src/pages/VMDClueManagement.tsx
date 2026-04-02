/**
 * VMD 线索管理页面
 * 筛选 + 表格/看板切换 + 线索详情 + 跟进时间线 + 新增 + 转化客户
 */

import React, { useState, useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import {
  Plus,
  Search,
  Target,
  LayoutList,
  Columns3,
  Loader2,
  MessageSquarePlus,
  UserCheck,
  Building2,
  Clock,
  Trash2,
} from 'lucide-react';
import {
  useVMDClues,
  useCreateVMDClue,
  useAddFollowUp,
  useConvertClue,
  useDeleteVMDClue,
  type VMDClue,
} from '@/hooks/useVMD';
import { useAuth } from '@/components/auth/AuthContext';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { toast } from 'sonner';

// ---------- 配置 ----------

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  new: { label: '新线索', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' },
  following: { label: '跟进中', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300' },
  high_intent: { label: '高意向', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300' },
  key_customer: { label: '重点客户', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300' },
  converted: { label: '已转化', color: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' },
};

const LEVEL_CONFIG: Record<string, { label: string; color: string }> = {
  A: { label: 'A级', color: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' },
  B: { label: 'B级', color: 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300' },
  C: { label: 'C级', color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300' },
  D: { label: 'D级', color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300' },
};

const SOURCE_OPTIONS = [
  { value: 'website', label: '官网' },
  { value: 'exhibition', label: '展会' },
  { value: 'referral', label: '转介绍' },
  { value: 'bid', label: '招投标' },
  { value: 'social_media', label: '社交媒体' },
  { value: 'cold_call', label: '电话拓客' },
  { value: 'other', label: '其他' },
];

const SOURCE_NAMES: Record<string, string> = Object.fromEntries(SOURCE_OPTIONS.map(s => [s.value, s.label]));

const KANBAN_COLUMNS = ['new', 'following', 'high_intent', 'key_customer', 'converted'];

function formatAmount(amount: number | null) {
  if (amount === null || amount === undefined) return '-';
  return `${(Number(amount) / 10000).toFixed(1)}万`;
}

// ---------- 组件 ----------

export default function VMDClueManagement() {
  // View mode: table or kanban
  const [viewMode, setViewMode] = useState<'table' | 'kanban'>('table');

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [levelFilter, setLevelFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [searchText, setSearchText] = useState('');

  // Dialog states
  const [createOpen, setCreateOpen] = useState(false);
  const [detailClue, setDetailClue] = useState<VMDClue | null>(null);
  const [followUpOpen, setFollowUpOpen] = useState(false);
  const [followUpContent, setFollowUpContent] = useState('');

  // Create form
  const [formCompany, setFormCompany] = useState('');
  const [formTitle, setFormTitle] = useState('');
  const [formSource, setFormSource] = useState('website');
  const [formLevel, setFormLevel] = useState('C');
  const [formAmount, setFormAmount] = useState('');

  // Queries & Mutations
  const { data: clues, isLoading } = useVMDClues({
    status: statusFilter !== 'all' ? statusFilter : undefined,
    level: levelFilter !== 'all' ? levelFilter : undefined,
    source: sourceFilter !== 'all' ? sourceFilter : undefined,
    search: searchText || undefined,
  });
  const createClue = useCreateVMDClue();
  const addFollowUp = useAddFollowUp();
  const convertClue = useConvertClue();
  const deleteClue = useDeleteVMDClue();
  const { role } = useAuth();
  const canDelete = role === 'boss' || role === 'admin';
  const { confirm, ConfirmDialog } = useConfirmDialog();

  // Local search filter
  const filteredClues = useMemo(() => {
    if (!clues) return [];
    if (!searchText) return clues;
    const lower = searchText.toLowerCase();
    return clues.filter(c =>
      c.company_name.toLowerCase().includes(lower) ||
      c.title.toLowerCase().includes(lower)
    );
  }, [clues, searchText]);

  // Group by status for kanban
  const kanbanGroups = useMemo(() => {
    const groups: Record<string, VMDClue[]> = {};
    KANBAN_COLUMNS.forEach(col => { groups[col] = []; });
    (filteredClues || []).forEach(c => {
      if (groups[c.status]) groups[c.status].push(c);
      else if (groups['new']) groups['new'].push(c);
    });
    return groups;
  }, [filteredClues]);

  const handleCreate = async () => {
    if (!formCompany.trim() || !formTitle.trim()) {
      toast.error('请填写公司名称和线索标题');
      return;
    }
    await createClue.mutateAsync({
      company_name: formCompany,
      title: formTitle,
      source: formSource,
      level: formLevel as VMDClue['level'],
      amount: formAmount ? Number(formAmount) : null,
    });
    setCreateOpen(false);
    setFormCompany('');
    setFormTitle('');
    setFormSource('website');
    setFormLevel('C');
    setFormAmount('');
  };

  const handleAddFollowUp = async () => {
    if (!detailClue || !followUpContent.trim()) return;
    await addFollowUp.mutateAsync({ clue_id: detailClue.id, content: followUpContent });
    setFollowUpContent('');
    setFollowUpOpen(false);
  };

  const handleConvert = async (clue: VMDClue) => {
    if (!(await confirm(`确定要将线索"${clue.company_name}"转化为正式客户吗？`))) return;
    await convertClue.mutateAsync(clue.id);
    setDetailClue(null);
  };

  const handleDeleteClue = async (clue: VMDClue) => {
    const ok = await confirm({
      title: '确认删除线索',
      description: `确定要删除线索「${clue.company_name}」吗？此操作不可撤销。`,
      variant: 'destructive',
      confirmText: '删除',
    });
    if (ok) {
      await deleteClue.mutateAsync(clue.id);
      setDetailClue(null);
    }
  };

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">线索管理</h1>
          <p className="text-muted-foreground">跟踪和管理所有营销线索，推动转化</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-lg border bg-muted/30 p-0.5">
            <Button
              variant={viewMode === 'table' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 px-2"
              onClick={() => setViewMode('table')}
            >
              <LayoutList className="w-3.5 h-3.5 mr-1" /> 列表
            </Button>
            <Button
              variant={viewMode === 'kanban' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 px-2"
              onClick={() => setViewMode('kanban')}
            >
              <Columns3 className="w-3.5 h-3.5 mr-1" /> 看板
            </Button>
          </div>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            新增线索
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="搜索公司名称或线索标题..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[130px]">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={levelFilter} onValueChange={setLevelFilter}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="全部等级" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部等级</SelectItem>
                {Object.entries(LEVEL_CONFIG).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="w-[130px]">
                <SelectValue placeholder="全部来源" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部来源</SelectItem>
                {SOURCE_OPTIONS.map(s => (
                  <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Content Area */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      ) : filteredClues.length === 0 ? (
        <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed">
          <Target className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium">暂无线索</h3>
          <p className="text-muted-foreground mb-6">开始录入您的第一条营销线索</p>
          <Button variant="outline" onClick={() => setCreateOpen(true)}>
            <Plus className="w-4 h-4 mr-2" /> 新增线索
          </Button>
        </div>
      ) : viewMode === 'table' ? (
        /* ====== Table View ====== */
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/30">
                  <th className="text-left p-3 text-xs font-medium text-muted-foreground">公司/标题</th>
                  <th className="text-left p-3 text-xs font-medium text-muted-foreground">来源</th>
                  <th className="text-left p-3 text-xs font-medium text-muted-foreground">状态</th>
                  <th className="text-left p-3 text-xs font-medium text-muted-foreground">等级</th>
                  <th className="text-left p-3 text-xs font-medium text-muted-foreground">预估金额</th>
                  <th className="text-left p-3 text-xs font-medium text-muted-foreground">负责人</th>
                  <th className="text-left p-3 text-xs font-medium text-muted-foreground">创建时间</th>
                </tr>
              </thead>
              <tbody>
                {filteredClues.map((clue) => {
                  const statusCfg = STATUS_CONFIG[clue.status] || STATUS_CONFIG.new;
                  const levelCfg = LEVEL_CONFIG[clue.level] || LEVEL_CONFIG.C;
                  return (
                    <tr
                      key={clue.id}
                      className="border-b last:border-b-0 hover:bg-muted/20 transition-colors cursor-pointer"
                      onClick={() => setDetailClue(clue)}
                    >
                      <td className="p-3">
                        <div>
                          <p className="text-sm font-medium">{clue.company_name}</p>
                          <p className="text-xs text-muted-foreground truncate max-w-[200px]">{clue.title}</p>
                        </div>
                      </td>
                      <td className="p-3">
                        <Badge variant="outline" className="text-xs">
                          {SOURCE_NAMES[clue.source] || clue.source}
                        </Badge>
                      </td>
                      <td className="p-3">
                        <Badge className={cn("text-[10px]", statusCfg.color)}>{statusCfg.label}</Badge>
                      </td>
                      <td className="p-3">
                        <Badge className={cn("text-[10px]", levelCfg.color)}>{levelCfg.label}</Badge>
                      </td>
                      <td className="p-3 text-sm">{formatAmount(clue.amount)}</td>
                      <td className="p-3 text-sm text-muted-foreground">{clue.assigned_to || '未分配'}</td>
                      <td className="p-3 text-xs text-muted-foreground">
                        {new Date(clue.created_at).toLocaleDateString('zh-CN')}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        /* ====== Kanban View ====== */
        <div className="flex gap-4 overflow-x-auto pb-4">
          {KANBAN_COLUMNS.map((col) => {
            const statusCfg = STATUS_CONFIG[col] || STATUS_CONFIG.new;
            const items = kanbanGroups[col] || [];
            return (
              <div
                key={col}
                className="flex-shrink-0 w-[280px] bg-muted/20 rounded-xl p-3 border border-border/50"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Badge className={cn("text-xs", statusCfg.color)}>{statusCfg.label}</Badge>
                    <span className="text-xs text-muted-foreground">{items.length}</span>
                  </div>
                </div>
                <div className="space-y-2 max-h-[500px] overflow-y-auto">
                  {items.map((clue) => {
                    const levelCfg = LEVEL_CONFIG[clue.level] || LEVEL_CONFIG.C;
                    return (
                      <Card
                        key={clue.id}
                        className="cursor-pointer hover:shadow-md transition-all hover:border-primary/50"
                        onClick={() => setDetailClue(clue)}
                      >
                        <CardContent className="p-3">
                          <div className="flex items-start justify-between mb-2">
                            <p className="text-sm font-medium line-clamp-1">{clue.company_name}</p>
                            <Badge className={cn("text-[10px] shrink-0 ml-1", levelCfg.color)}>
                              {levelCfg.label}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{clue.title}</p>
                          <div className="flex items-center justify-between">
                            <Badge variant="outline" className="text-[10px]">
                              {SOURCE_NAMES[clue.source] || clue.source}
                            </Badge>
                            {clue.amount != null && (
                              <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                                {formatAmount(clue.amount)}
                              </span>
                            )}
                          </div>
                          {clue.follow_ups && clue.follow_ups.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-border/50 text-[10px] text-muted-foreground flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {clue.follow_ups.length} 条跟进
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                  {items.length === 0 && (
                    <p className="text-xs text-muted-foreground text-center py-6">暂无线索</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ====== Create Clue Dialog ====== */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>新增线索</DialogTitle>
            <DialogDescription>录入新的营销线索信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>公司名称</Label>
              <Input
                placeholder="例如：某某科技有限公司"
                value={formCompany}
                onChange={(e) => setFormCompany(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>线索标题</Label>
              <Input
                placeholder="例如：Q2采购需求咨询"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>线索来源</Label>
                <Select value={formSource} onValueChange={setFormSource}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {SOURCE_OPTIONS.map(s => (
                      <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>线索等级</Label>
                <Select value={formLevel} onValueChange={setFormLevel}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(LEVEL_CONFIG).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>预估金额（元，可选）</Label>
              <Input
                type="number"
                placeholder="0"
                value={formAmount}
                onChange={(e) => setFormAmount(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button onClick={handleCreate} disabled={createClue.isPending}>
              {createClue.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              创建线索
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ====== Detail Sheet ====== */}
      <Sheet open={!!detailClue} onOpenChange={(open) => { if (!open) setDetailClue(null); }}>
        <SheetContent className="w-full sm:max-w-xl overflow-hidden flex flex-col">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Building2 className="w-5 h-5" />
              {detailClue?.company_name}
            </SheetTitle>
            <SheetDescription>{detailClue?.title}</SheetDescription>
          </SheetHeader>
          <ScrollArea className="flex-1 mt-4 -mx-6 px-6">
            {detailClue && (
              <div className="space-y-6 pb-6">
                {/* Badges */}
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge className={cn(STATUS_CONFIG[detailClue.status]?.color)}>
                    {STATUS_CONFIG[detailClue.status]?.label}
                  </Badge>
                  <Badge className={cn(LEVEL_CONFIG[detailClue.level]?.color)}>
                    {LEVEL_CONFIG[detailClue.level]?.label}
                  </Badge>
                  <Badge variant="outline">{SOURCE_NAMES[detailClue.source] || detailClue.source}</Badge>
                </div>

                {/* Info Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">预估金额</p>
                    <p className="text-sm font-medium">
                      {detailClue.amount != null ? `${(detailClue.amount / 10000).toFixed(1)} 万元` : '未设置'}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">负责人</p>
                    <p className="text-sm font-medium">{detailClue.assigned_to || '未分配'}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">创建时间</p>
                    <p className="text-sm">{new Date(detailClue.created_at).toLocaleString('zh-CN')}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">更新时间</p>
                    <p className="text-sm">{new Date(detailClue.updated_at).toLocaleString('zh-CN')}</p>
                  </div>
                </div>

                <Separator />

                {/* Follow-up Timeline */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium">跟进记录</h4>
                    <Button size="sm" variant="outline" onClick={() => setFollowUpOpen(true)}>
                      <MessageSquarePlus className="w-3.5 h-3.5 mr-1" /> 添加跟进
                    </Button>
                  </div>
                  {detailClue.follow_ups && detailClue.follow_ups.length > 0 ? (
                    <div className="space-y-3">
                      {detailClue.follow_ups.map((fu, idx) => (
                        <div key={fu.id} className="relative pl-6">
                          {/* Timeline dot */}
                          <div className="absolute left-0 top-1.5 w-3 h-3 rounded-full bg-primary/30 border-2 border-primary" />
                          {idx < detailClue.follow_ups.length - 1 && (
                            <div className="absolute left-[5px] top-4 bottom-0 w-0.5 bg-border" />
                          )}
                          <div className="bg-muted/30 rounded-lg p-3">
                            <p className="text-sm whitespace-pre-wrap">{fu.content}</p>
                            <p className="text-[10px] text-muted-foreground mt-2">
                              {new Date(fu.created_at).toLocaleString('zh-CN')}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-4">暂无跟进记录</p>
                  )}
                </div>

                <Separator />

                {/* Actions */}
                <div className="flex gap-2">
                  {detailClue.status !== 'converted' && (
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => handleConvert(detailClue)}
                      disabled={convertClue.isPending}
                    >
                      {convertClue.isPending ? (
                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                      ) : (
                        <UserCheck className="w-4 h-4 mr-1" />
                      )}
                      转化为客户
                    </Button>
                  )}
                  {canDelete && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                      onClick={() => handleDeleteClue(detailClue)}
                      disabled={deleteClue.isPending}
                    >
                      <Trash2 className="w-4 h-4 mr-1" /> 删除线索
                    </Button>
                  )}
                </div>
              </div>
            )}
          </ScrollArea>
        </SheetContent>
      </Sheet>

      {/* ====== Add Follow-Up Dialog ====== */}
      <Dialog open={followUpOpen} onOpenChange={setFollowUpOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>添加跟进记录</DialogTitle>
            <DialogDescription>{detailClue?.company_name}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <Textarea
              placeholder="记录本次跟进的内容..."
              rows={4}
              value={followUpContent}
              onChange={(e) => setFollowUpContent(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFollowUpOpen(false)}>取消</Button>
            <Button onClick={handleAddFollowUp} disabled={addFollowUp.isPending}>
              {addFollowUp.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {ConfirmDialog}
    </div>
  );
}

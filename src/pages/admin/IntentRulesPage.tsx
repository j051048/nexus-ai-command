/**
 * IntentRulesPage - 行业术语/意图关键词管理
 *
 * 管理员可动态添加、修改、删除意图识别关键词，
 * 扩展 AI 的意图分类能力，无需修改代码。
 */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { LoadingState } from '@/components/common/LoadingState';
import { NoDataYet } from '@/components/common/EmptyState';
import { Plus, Pencil, Trash2, Brain, Loader2, Search } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { typography } from '@/lib/design-tokens';

interface IntentRule {
  id: string;
  keyword: string;
  complexity: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

const COMPLEXITY_LABELS: Record<string, { label: string; color: string }> = {
  critical: { label: '关键', color: 'bg-red-500/10 text-red-500 border-red-500/20' },
  complex: { label: '复杂', color: 'bg-purple-500/10 text-purple-500 border-purple-500/20' },
  moderate: { label: '中等', color: 'bg-blue-500/10 text-blue-500 border-blue-500/20' },
};

function useIntentRules() {
  return useQuery({
    queryKey: ['intent-rules'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: IntentRule[] }>('api/intent-rules');
      return res.data;
    },
  });
}

export default function IntentRulesPage() {
  const qc = useQueryClient();
  const { data: rules, isLoading } = useIntentRules();
  const [searchQuery, setSearchQuery] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<IntentRule | null>(null);
  const [form, setForm] = useState({ keyword: '', complexity: 'moderate', description: '', is_active: true });

  const createMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      await aiClient.fetch('api/intent-rules', { method: 'POST', body: JSON.stringify(data) });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['intent-rules'] });
      toast.success('规则创建成功');
      closeDialog();
    },
    onError: () => toast.error('创建失败'),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<typeof form> }) => {
      await aiClient.fetch(`api/intent-rules/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['intent-rules'] });
      toast.success('规则更新成功');
      closeDialog();
    },
    onError: () => toast.error('更新失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await aiClient.fetch(`api/intent-rules/${id}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['intent-rules'] });
      toast.success('规则已删除');
    },
    onError: () => toast.error('删除失败'),
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      await aiClient.fetch(`api/intent-rules/${id}`, { method: 'PUT', body: JSON.stringify({ is_active }) });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['intent-rules'] });
    },
  });

  const closeDialog = () => {
    setDialogOpen(false);
    setEditing(null);
    setForm({ keyword: '', complexity: 'moderate', description: '', is_active: true });
  };

  const openCreate = () => {
    setEditing(null);
    setForm({ keyword: '', complexity: 'moderate', description: '', is_active: true });
    setDialogOpen(true);
  };

  const openEdit = (rule: IntentRule) => {
    setEditing(rule);
    setForm({
      keyword: rule.keyword,
      complexity: rule.complexity,
      description: rule.description || '',
      is_active: rule.is_active,
    });
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (!form.keyword.trim()) {
      toast.error('请输入关键词');
      return;
    }
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: form });
    } else {
      createMutation.mutate(form);
    }
  };

  const filteredRules = (rules || []).filter(r =>
    !searchQuery || r.keyword.includes(searchQuery) || r.description?.includes(searchQuery)
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className={cn(typography.h1)}>意图规则管理</h1>
          <p className={cn(typography.small, 'text-muted-foreground mt-1')}>
            管理 AI 意图识别的关键词规则，动态扩展业务术语
          </p>
        </div>
        <Button className="gap-2" onClick={openCreate}>
          <Plus className="w-4 h-4" />
          添加规则
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          placeholder="搜索关键词..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Rules List */}
      {isLoading ? (
        <LoadingState type="skeleton" rows={5} message="加载规则..." />
      ) : filteredRules.length === 0 ? (
        <NoDataYet
          resourceName="意图规则"
          description="添加行业术语关键词，AI 将自动识别相关意图并分配对应的处理流程。"
          onAdd={openCreate}
        />
      ) : (
        <div className="grid gap-3">
          {filteredRules.map(rule => (
            <Card key={rule.id} className={cn(!rule.is_active && 'opacity-50')}>
              <CardContent className="py-3 px-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <Brain className="w-4 h-4 text-purple-500 shrink-0" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{rule.keyword}</span>
                      <Badge variant="outline" className={cn('text-[10px]', COMPLEXITY_LABELS[rule.complexity]?.color)}>
                        {COMPLEXITY_LABELS[rule.complexity]?.label || rule.complexity}
                      </Badge>
                    </div>
                    {rule.description && (
                      <p className="text-xs text-muted-foreground truncate">{rule.description}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Switch
                    checked={rule.is_active}
                    onCheckedChange={checked => toggleMutation.mutate({ id: rule.id, is_active: checked })}
                    className="scale-75"
                  />
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => openEdit(rule)}>
                    <Pencil className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                    onClick={() => {
                      if (confirm(`确认删除规则「${rule.keyword}」？`)) {
                        deleteMutation.mutate(rule.id);
                      }
                    }}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={closeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? '编辑规则' : '添加规则'}</DialogTitle>
            <DialogDescription>
              {editing ? '修改意图识别关键词规则' : '添加新的意图识别关键词，保存后立即生效'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>关键词 *</Label>
              <Input
                value={form.keyword}
                onChange={e => setForm({ ...form, keyword: e.target.value })}
                placeholder="如：出差、采购申请、合同审批"
              />
            </div>
            <div className="space-y-2">
              <Label>复杂度</Label>
              <Select value={form.complexity} onValueChange={v => setForm({ ...form, complexity: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="moderate">中等 — 单工具查询</SelectItem>
                  <SelectItem value="complex">复杂 — 多步骤分析</SelectItem>
                  <SelectItem value="critical">关键 — 涉及审批/财务</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>描述（可选）</Label>
              <Input
                value={form.description}
                onChange={e => setForm({ ...form, description: e.target.value })}
                placeholder="简要描述此关键词的业务含义"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>取消</Button>
            <Button
              onClick={handleSubmit}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {(createMutation.isPending || updateMutation.isPending) && (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              )}
              {editing ? '保存' : '添加'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

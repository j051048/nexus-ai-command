import { getApiBaseUrl } from "@/lib/apiConfig";
import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/components/auth/AuthContext';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';
import {
  Shield,
  Plus,
  Trash2,
  Save,
  Loader2,
  BookOpen,
  AlertTriangle,
} from 'lucide-react';

const API_BASE_URL = getApiBaseUrl();

interface PolicyEntry {
  id?: string;
  key: string;
  value: string;
  isNew?: boolean;
}

async function authFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  let baseUrl = API_BASE_URL;
  if (!baseUrl.startsWith('http')) {
    baseUrl = baseUrl.includes('localhost') ? `http://${baseUrl}` : `https://${baseUrl}`;
  }
  const cleanBase = baseUrl.replace(/\/$/, '');
  const cleanEndpoint = url.startsWith('/') ? url.slice(1) : url;
  const fullUrl = `${cleanBase}/${cleanEndpoint}`;

  const response = await fetch(fullUrl, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string>),
    },
  });

  if (!response.ok) {
    let errorMessage = `请求失败 (${response.status})`;
    try {
      const errorData = await response.json();
      if (errorData.error?.message) errorMessage = errorData.error.message;
      else if (typeof errorData.detail === 'string') errorMessage = errorData.detail;
    } catch {
      // ignore
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

const PRESET_TEMPLATES: PolicyEntry[] = [
  { key: '合规底线', value: '所有审批必须符合公司《内控制度》，超过5万元的支出需要总经理审批', isNew: true },
  { key: '沟通风格', value: '回复客户时使用正式商务语气，避免口语化表达', isNew: true },
  { key: '数据安全', value: '禁止在对话中透露公司未公开的财务数据、客户名单和商业机密', isNew: true },
  { key: '审批规则', value: '员工请假超过3天需提前一周申请，出差报销须附发票原件', isNew: true },
];

export function OrgPolicyEditor() {
  const { role } = useAuth();
  const [policies, setPolicies] = useState<PolicyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const isAdmin = role === 'boss' || role === 'manager';

  // Fetch existing policies
  useEffect(() => {
    fetchPolicies();
  }, []);

  const fetchPolicies = async () => {
    setLoading(true);
    try {
      const result = await authFetch<{ data: PolicyEntry[] }>('api/memories/org-policies');
      setPolicies(result.data?.map(p => ({ ...p, isNew: false })) || []);
    } catch (err) {
      console.warn('Failed to fetch org policies:', err);
    } finally {
      setLoading(false);
    }
  };

  const addPolicy = () => {
    setPolicies(prev => [...prev, { key: '', value: '', isNew: true }]);
  };

  const removePolicy = async (index: number) => {
    const policy = policies[index];

    // If it has an ID (saved in DB), delete from server
    if (policy.id) {
      try {
        await authFetch(`api/memories/org-policies/${policy.id}`, { method: 'DELETE' });
        toast.success('准则已删除');
      } catch (err) {
        toast.error(err instanceof Error ? err.message : '删除失败');
        return;
      }
    }

    setPolicies(prev => prev.filter((_, i) => i !== index));
  };

  const updatePolicy = (index: number, field: 'key' | 'value', val: string) => {
    setPolicies(prev => prev.map((p, i) => i === index ? { ...p, [field]: val } : p));
  };

  const handleSave = async () => {
    const valid = policies.filter(p => p.key.trim() && p.value.trim());
    if (valid.length === 0) {
      toast.error('请至少添加一条行为准则');
      return;
    }

    setSaving(true);
    try {
      await authFetch('api/memories/org-policies', {
        method: 'PUT',
        body: JSON.stringify({
          policies: valid.map(p => ({ key: p.key.trim(), value: p.value.trim() })),
        }),
      });
      toast.success(`已保存 ${valid.length} 条组织行为准则`);
      await fetchPolicies(); // Refresh to get IDs
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const loadTemplate = (template: PolicyEntry) => {
    // Avoid duplicate keys
    if (policies.some(p => p.key === template.key)) {
      toast.info(`"${template.key}" 已存在`);
      return;
    }
    setPolicies(prev => [...prev, { ...template }]);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="w-5 h-5" />
            组织行为准则
          </CardTitle>
          <CardDescription>
            定义 AI 助手在所有对话中必须遵守的组织规则。这些准则会在每次对话时自动注入，优先级最高。
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!isAdmin && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-warning/10 text-warning text-sm mb-4">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              仅管理员可编辑组织行为准则，当前为只读模式
            </div>
          )}

          {/* Policy list */}
          <div className="space-y-3">
            {policies.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-40" />
                <p className="text-sm">尚未设置组织行为准则</p>
                <p className="text-xs mt-1">AI 助手将使用默认行为模式</p>
              </div>
            )}

            {policies.map((policy, index) => (
              <div key={index} className="flex gap-3 items-start p-3 rounded-lg border border-border bg-muted/20">
                <div className="flex-1 space-y-2">
                  <Input
                    placeholder="准则名称（如：合规底线、沟通风格）"
                    value={policy.key}
                    onChange={(e) => updatePolicy(index, 'key', e.target.value)}
                    disabled={!isAdmin}
                    className="font-medium"
                  />
                  <Textarea
                    placeholder="具体规则描述..."
                    value={policy.value}
                    onChange={(e) => updatePolicy(index, 'value', e.target.value)}
                    disabled={!isAdmin}
                    rows={2}
                  />
                </div>
                {isAdmin && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removePolicy(index)}
                    className="shrink-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                )}
              </div>
            ))}
          </div>

          {/* Actions */}
          {isAdmin && (
            <div className="flex gap-3 pt-4">
              <Button variant="outline" onClick={addPolicy} className="gap-2">
                <Plus className="w-4 h-4" />
                添加准则
              </Button>
              <Button onClick={handleSave} disabled={saving} className="gap-2">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                保存全部
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Preset templates */}
      {isAdmin && (
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="text-base">快速模板</CardTitle>
            <CardDescription>点击添加常用的组织行为准则模板</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {PRESET_TEMPLATES.map((tpl) => (
                <Button
                  key={tpl.key}
                  variant="outline"
                  size="sm"
                  onClick={() => loadTemplate(tpl)}
                  className="gap-1.5"
                >
                  <Plus className="w-3 h-3" />
                  {tpl.key}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Explanation card */}
      <Card className="border-border bg-muted/30">
        <CardContent className="pt-4">
          <div className="flex items-start gap-3">
            <Badge variant="outline" className="bg-primary/10 shrink-0 mt-0.5">
              工作原理
            </Badge>
            <div className="text-sm text-muted-foreground space-y-1">
              <p>组织行为准则会在 AI 助手每次对话时自动注入到系统提示词的最前面，确保 AI 始终遵守这些规则。</p>
              <p>例如：如果您设置了"所有审批必须符合内控制度"，AI 在处理审批相关问题时会主动参考此规则。</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

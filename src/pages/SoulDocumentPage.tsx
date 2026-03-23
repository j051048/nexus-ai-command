import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Brain, Eye, Save, Loader2, ShieldAlert } from 'lucide-react';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { getApiBaseUrl } from '@/lib/apiConfig';

interface SoulDocument {
  ai_name: string;
  identity: string;
  personality: string;
  values: string;
  language_style: string;
  taboos: string;
  custom_instructions: string;
  is_active: boolean;
}

const DEFAULT_DOC: SoulDocument = {
  ai_name: '小助手',
  identity: '',
  personality: '',
  values: '',
  language_style: '',
  taboos: '',
  custom_instructions: '',
  is_active: true,
};

async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

function SoulDocumentPage() {
  const { profile } = useAuth();
  const userRole = (profile as Record<string, unknown>)?.role as string | undefined;
  const canEdit = userRole === 'boss' || userRole === 'founder';

  const [doc, setDoc] = useState<SoulDocument>(DEFAULT_DOC);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const API_BASE = getApiBaseUrl();

  const loadDoc = useCallback(async () => {
    try {
      setLoading(true);
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/soul-document`, { headers });
      const json = await res.json();
      if (json.data) {
        setDoc({
          ai_name: json.data.ai_name || '小助手',
          identity: json.data.identity || '',
          personality: json.data.personality || '',
          values: json.data.values || '',
          language_style: json.data.language_style || '',
          taboos: json.data.taboos || '',
          custom_instructions: json.data.custom_instructions || '',
          is_active: json.data.is_active ?? true,
        });
      }
    } catch {
      // 未配置灵魂文档是正常情况
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    loadDoc();
  }, [loadDoc]);

  const handleSave = async () => {
    try {
      setSaving(true);
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/soul-document`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(doc),
      });
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json.message || '保存失败');
      }
      toast.success('灵魂文档已保存');
      setPreview(null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async () => {
    try {
      setPreviewing(true);
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/soul-document/preview`, { headers });
      const json = await res.json();
      setPreview(json.data?.compiled || '尚未配置灵魂文档');
    } catch {
      toast.error('预览失败');
    } finally {
      setPreviewing(false);
    }
  };

  const updateField = (field: keyof SoulDocument, value: string | boolean) => {
    setDoc(prev => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Brain className="w-6 h-6" />
            AI 灵魂文档
          </h1>
          <p className="text-muted-foreground mt-1">
            定义 AI 助手的核心人格、价值观和行为准则
          </p>
        </div>
        {!canEdit && (
          <div className="flex items-center gap-2 text-amber-600 bg-amber-50 dark:bg-amber-950/30 px-3 py-2 rounded-lg text-sm">
            <ShieldAlert className="w-4 h-4" />
            需要管理员权限编辑
          </div>
        )}
      </div>

      {/* 基础设置 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">基础设置</CardTitle>
          <CardDescription>定义 AI 助手的名字和启用状态</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label>启用灵魂文档</Label>
              <p className="text-sm text-muted-foreground">关闭后 AI 将使用系统默认人格</p>
            </div>
            <Switch
              checked={doc.is_active}
              onCheckedChange={v => updateField('is_active', v)}
              disabled={!canEdit}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="ai_name">AI 名字</Label>
            <Input
              id="ai_name"
              value={doc.ai_name}
              onChange={e => updateField('ai_name', e.target.value)}
              placeholder="如：小慧、Nexus、阿尔法"
              maxLength={50}
              disabled={!canEdit}
            />
            <p className="text-xs text-muted-foreground">员工会用这个名字称呼 AI 助手</p>
          </div>
        </CardContent>
      </Card>

      {/* 人格定义 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">人格定义</CardTitle>
          <CardDescription>塑造 AI 助手的性格和说话方式</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="identity">身份定位</Label>
            <Textarea
              id="identity"
              value={doc.identity}
              onChange={e => updateField('identity', e.target.value)}
              placeholder="如：你是XX公司的智能管家，像一位经验丰富的行政总监"
              rows={2}
              maxLength={500}
              disabled={!canEdit}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="personality">性格特征</Label>
            <Textarea
              id="personality"
              value={doc.personality}
              onChange={e => updateField('personality', e.target.value)}
              placeholder="如：温暖亲和、专业高效、有幽默感但不轻浮"
              rows={2}
              maxLength={500}
              disabled={!canEdit}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="language_style">语言风格</Label>
            <Input
              id="language_style"
              value={doc.language_style}
              onChange={e => updateField('language_style', e.target.value)}
              placeholder="如：正式商务 / 轻松活泼 / 干练简洁"
              maxLength={500}
              disabled={!canEdit}
            />
          </div>
        </CardContent>
      </Card>

      {/* 价值观与红线 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">价值观与红线</CardTitle>
          <CardDescription>设定 AI 助手必须遵守的原则和绝对不可触碰的禁区</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="values">价值观 / 行为准则</Label>
            <Textarea
              id="values"
              value={doc.values}
              onChange={e => updateField('values', e.target.value)}
              placeholder="如：客户第一、数据驱动、诚实透明、追求极致"
              rows={3}
              maxLength={1000}
              disabled={!canEdit}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="taboos">禁忌 / 红线</Label>
            <Textarea
              id="taboos"
              value={doc.taboos}
              onChange={e => updateField('taboos', e.target.value)}
              placeholder="如：绝不贬低竞品、不承诺无法兑现的事项、不泄露内部定价策略"
              rows={3}
              maxLength={1000}
              disabled={!canEdit}
            />
          </div>
        </CardContent>
      </Card>

      {/* 自由指令区 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">自由指令区</CardTitle>
          <CardDescription>
            在这里写任何额外的企业特色指令、行业知识、特殊规则
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            value={doc.custom_instructions}
            onChange={e => updateField('custom_instructions', e.target.value)}
            placeholder="如：我们是一家科学仪器公司，产品线包括XX和YY。回答客户问题时需要注意..."
            rows={6}
            maxLength={3000}
            disabled={!canEdit}
          />
          <p className="text-xs text-muted-foreground mt-1">
            {doc.custom_instructions.length}/3000
          </p>
        </CardContent>
      </Card>

      {/* 预览 */}
      {preview && (
        <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Eye className="w-5 h-5" />
              编译预览
            </CardTitle>
            <CardDescription>这是 AI 实际接收到的灵魂指令</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-sm font-mono bg-background rounded-lg p-4 border">
              {preview}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* 操作按钮 */}
      {canEdit && (
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={handlePreview} disabled={previewing}>
            {previewing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Eye className="w-4 h-4 mr-2" />}
            预览效果
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
            保存
          </Button>
        </div>
      )}
    </div>
  );
}

export default SoulDocumentPage;

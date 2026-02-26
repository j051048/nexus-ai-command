import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import {
  Key,
  Plus,
  Copy,
  Trash2,
  BarChart3,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { supabase } from '@/integrations/supabase/client';

// ============== Types ==============

interface APIKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string;
  last_used_at: string | null;
  usage_count: number;
  created_at: string;
}

interface CreatedKey {
  id: string;
  name: string;
  key: string;
  key_prefix: string;
  scopes: string[];
  expires_at: string;
  warning: string;
}

// ============== API Helpers ==============

const API_BASE = `${import.meta.env.VITE_API_BASE_URL}/api/api-keys`;

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token || '';
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    ...options,
  });
  if (!res.ok) throw new Error(`API 请求失败: ${res.status}`);
  const json = await res.json();
  return json.data ?? json;
}

// ============== Scope Options ==============

const SCOPE_OPTIONS = [
  { value: 'read', label: '读取', desc: '读取数据' },
  { value: 'write', label: '写入', desc: '创建和更新数据' },
  { value: 'approval', label: '审批', desc: '审批流程操作' },
  { value: 'ai', label: 'AI', desc: 'AI 服务调用' },
  { value: 'admin', label: '管理', desc: '完整管理权限' },
];

const EXPIRE_OPTIONS = [
  { value: '30', label: '30 天' },
  { value: '90', label: '90 天' },
  { value: '180', label: '180 天' },
  { value: '365', label: '1 年' },
  { value: '730', label: '2 年' },
];

// ============== Component ==============

function APIKeysPage() {
  const [keys, setKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createdKey, setCreatedKey] = useState<CreatedKey | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<APIKey | null>(null);
  const [copied, setCopied] = useState(false);

  // 创建表单
  const [newName, setNewName] = useState('');
  const [newScopes, setNewScopes] = useState<string[]>(['read']);
  const [newExpireDays, setNewExpireDays] = useState('365');

  // ---------- 加载 ----------

  const loadKeys = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchAPI<APIKey[]>('');
      setKeys(Array.isArray(data) ? data : []);
    } catch (e) {
      toast.error('加载 API Keys 失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  // ---------- 创建 ----------

  const handleCreate = async () => {
    if (!newName.trim()) {
      toast.error('请输入 Key 名称');
      return;
    }
    if (newScopes.length === 0) {
      toast.error('请选择至少一个权限范围');
      return;
    }

    try {
      const result = await fetchAPI<CreatedKey>('', {
        method: 'POST',
        body: JSON.stringify({
          name: newName.trim(),
          scopes: newScopes,
          expires_days: parseInt(newExpireDays, 10),
        }),
      });
      setCreatedKey(result);
      setShowCreate(false);
      setNewName('');
      setNewScopes(['read']);
      setNewExpireDays('365');
      toast.success('API Key 创建成功');
      loadKeys();
    } catch {
      toast.error('创建 API Key 失败');
    }
  };

  // ---------- 复制 ----------

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success('已复制到剪贴板');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('复制失败，请手动复制');
    }
  };

  // ---------- 撤销 ----------

  const handleRevoke = async () => {
    if (!revokeTarget) return;
    try {
      await fetchAPI(`/${revokeTarget.id}`, { method: 'DELETE' });
      toast.success('API Key 已撤销');
      setRevokeTarget(null);
      loadKeys();
    } catch {
      toast.error('撤销失败');
    }
  };

  // ---------- 权限范围切换 ----------

  const toggleScope = (scope: string) => {
    setNewScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  // ---------- Render ----------

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      {/* 标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Key className="w-7 h-7 text-primary" />
            API Keys 管理
          </h1>
          <p className="text-sm text-muted-foreground">
            管理开放 API 密钥，用于第三方系统集成
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadKeys}>
            <RefreshCw className="w-4 h-4 mr-1" />
            刷新
          </Button>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="w-4 h-4 mr-1" />
            创建 API Key
          </Button>
        </div>
      </div>

      {/* API 文档链接 */}
      <Card className="bg-muted/30 border-dashed">
        <CardContent className="p-4 flex items-center gap-3">
          <ExternalLink className="w-5 h-5 text-primary shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium">API 文档</p>
            <p className="text-xs text-muted-foreground">
              查看完整的 API 文档以了解如何使用 API Key 进行集成
            </p>
          </div>
          <Button variant="outline" size="sm" asChild>
            <a href="#" onClick={(e) => { e.preventDefault(); toast.info('API 文档功能即将上线'); }} rel="noopener noreferrer">
              查看文档
            </a>
          </Button>
        </CardContent>
      </Card>

      {/* Key 列表 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">密钥列表</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>Key 前缀</TableHead>
                  <TableHead>权限</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>使用次数</TableHead>
                  <TableHead>上次使用</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-12">
                      <Key className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>暂无 API Key</p>
                      <p className="text-xs mt-1">点击上方按钮创建您的第一个 API Key</p>
                    </TableCell>
                  </TableRow>
                ) : (
                  keys.map((key) => (
                    <TableRow key={key.id}>
                      <TableCell className="font-medium">{key.name}</TableCell>
                      <TableCell>
                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                          {key.key_prefix}...
                        </code>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {key.scopes.map((scope) => (
                            <Badge key={scope} variant="outline" className="text-xs">
                              {scope}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        {key.is_active ? (
                          <Badge className="bg-green-100 text-green-800">
                            <CheckCircle2 className="w-3 h-3 mr-1" />
                            活跃
                          </Badge>
                        ) : (
                          <Badge variant="secondary">
                            <XCircle className="w-3 h-3 mr-1" />
                            已撤销
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-sm">{key.usage_count.toLocaleString()}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {key.last_used_at
                          ? new Date(key.last_used_at).toLocaleDateString('zh-CN')
                          : '从未使用'}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" asChild>
                            <a href={`#usage-${key.id}`}>
                              <BarChart3 className="w-4 h-4" />
                            </a>
                          </Button>
                          {key.is_active && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              onClick={() => setRevokeTarget(key)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ========== 创建 Key 弹窗 ========== */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>创建 API Key</DialogTitle>
            <DialogDescription>创建新的 API 密钥用于系统集成</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label>名称</Label>
              <Input
                placeholder="例如: ERP 集成, 移动端 App..."
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>权限范围</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {SCOPE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => toggleScope(opt.value)}
                    className={`flex flex-col p-2 rounded-lg border text-left text-sm transition-colors ${
                      newScopes.includes(opt.value)
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-muted/50'
                    }`}
                  >
                    <span className="font-medium">{opt.label}</span>
                    <span className="text-xs text-muted-foreground">{opt.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>有效期</Label>
              <Select value={newExpireDays} onValueChange={setNewExpireDays}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {EXPIRE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              取消
            </Button>
            <Button onClick={handleCreate} disabled={!newName.trim() || newScopes.length === 0}>
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ========== 创建成功 - 显示 Key ========== */}
      <Dialog open={!!createdKey} onOpenChange={() => setCreatedKey(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-500" />
              API Key 创建成功
            </DialogTitle>
            <DialogDescription className="text-destructive font-medium">
              请立即复制并安全保存此 API Key，关闭后将无法再次查看完整内容！
            </DialogDescription>
          </DialogHeader>

          {createdKey && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>名称</Label>
                <p className="text-sm font-medium">{createdKey.name}</p>
              </div>

              <div className="space-y-2">
                <Label>API Key</Label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs bg-muted p-3 rounded-lg break-all font-mono select-all">
                    {createdKey.key}
                  </code>
                  <Button
                    variant="outline"
                    size="sm"
                    className="shrink-0"
                    onClick={() => handleCopy(createdKey.key)}
                  >
                    <Copy className="w-4 h-4 mr-1" />
                    {copied ? '已复制' : '复制'}
                  </Button>
                </div>
              </div>

              <div className="flex gap-3 text-sm">
                <div>
                  <span className="text-muted-foreground">权限: </span>
                  {createdKey.scopes.map((s) => (
                    <Badge key={s} variant="outline" className="text-xs mr-1">
                      {s}
                    </Badge>
                  ))}
                </div>
                <div>
                  <span className="text-muted-foreground">过期: </span>
                  <span>{new Date(createdKey.expires_at).toLocaleDateString('zh-CN')}</span>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button onClick={() => setCreatedKey(null)}>我已安全保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ========== 撤销确认 ========== */}
      <AlertDialog open={!!revokeTarget} onOpenChange={() => setRevokeTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认撤销 API Key？</AlertDialogTitle>
            <AlertDialogDescription>
              撤销后，使用此 Key 的所有集成将立即失效。此操作不可恢复。
              <br />
              <br />
              Key: <code className="text-xs bg-muted px-1 rounded">{revokeTarget?.key_prefix}...</code>
              {' '}({revokeTarget?.name})
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRevoke}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              确认撤销
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default APIKeysPage;

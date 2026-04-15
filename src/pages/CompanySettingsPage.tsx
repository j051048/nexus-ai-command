import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import {
  Building2,
  Copy,
  RefreshCw,
  CheckCircle2,
  Shield,
  Users,
  Loader2,
  Palette,
  Image,
  Type,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { httpClient } from '@/lib/httpClient';

interface OrgInfo {
  id: string;
  name: string;
  slug: string;
  invite_code: string | null;
  invite_code_enabled: boolean;
  invite_code_expires_at: string | null;
  member_count?: number;
}

interface ApiResponse<T> {
  status: number;
  message: string;
  data: T;
}

interface OrgDetailFromApi {
  id: string;
  name: string;
  slug: string;
  invite_code: string | null;
  invite_code_enabled: boolean;
  invite_code_expires_at: string | null;
}

// 安全提取字符串值（防止 React #301 崩溃）
function safeStr(v: unknown): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (typeof v === 'object') {
    const name = (v as Record<string, unknown>).name;
    if (typeof name === 'string') return name;
    return JSON.stringify(v);
  }
  return String(v);
}

function CompanySettingsPage() {
  const { profile } = useAuth();
  const orgId = profile?.organization_id;
  const [org, setOrg] = useState<OrgInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [orgName, setOrgName] = useState('');
  // Brand state
  const [brand, setBrand] = useState<Record<string, unknown>>({});
  const [savingBrand, setSavingBrand] = useState(false);

  // Load brand config
  const loadBrand = useCallback(async () => {
    if (!orgId) return;
    try {
      const res = await httpClient.get<ApiResponse<Record<string, unknown>>>('/api/organization/brand');
      setBrand(res.data?.data || {});
    } catch {
      // brand is optional, ignore errors
    }
  }, [orgId]);

  useEffect(() => {
    loadBrand();
  }, [loadBrand]);

  // Save brand config
  const handleSaveBrand = async () => {
    try {
      setSavingBrand(true);
      const res = await httpClient.put<ApiResponse<Record<string, unknown>>>('/api/organization/brand', { brand });
      if (res.data?.status !== 200) throw new Error(res.data?.message || '更新失败');
      toast.success('品牌配置已保存');
      setBrand(res.data.data || brand);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } }, message?: string };
      toast.error(`保存品牌配置失败: ${e.response?.data?.message || e.message || '未知错误'}`);
    } finally {
      setSavingBrand(false);
    }
  };

  // 版本标记：确认最新代码已加载 (v6 - 2026-04-15)
  useEffect(() => {
    console.log('[CompanySettingsPage] v6 loaded, profile:', profile?.id);
  }, [profile?.id]);

  // Load organization data
  const loadOrg = useCallback(async () => {
    if (!orgId) {
      console.warn('[CompanySettings] No organization_id found in profile');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      // 调用新的后端接口获取详情
      const response = await httpClient.get<ApiResponse<OrgDetailFromApi>>('/api/organization/detail');
      
      // 处理后端统一包装的 api_success 结构
      const orgDataFromApi = response.data?.data;
      
      if (!orgDataFromApi) {
        throw new Error('未获取到组织数据');
      }

      // 获取组织统计数据（可选，也可以扩展 detail 接口）
      let memberCount = 0;
      try {
        const statsResponse = await httpClient.get<ApiResponse<{ total_employees: number }>>('/api/organization/stats');
        memberCount = statsResponse.data?.data?.total_employees || 0;
      } catch (e) {
        console.warn('[CompanySettings] Failed to load stats:', e);
      }

      const orgData: OrgInfo = {
        id: orgDataFromApi.id,
        name: safeStr(orgDataFromApi.name),
        slug: safeStr(orgDataFromApi.slug),
        invite_code: orgDataFromApi.invite_code ? safeStr(orgDataFromApi.invite_code) : null,
        invite_code_enabled: orgDataFromApi.invite_code_enabled ?? true,
        invite_code_expires_at: orgDataFromApi.invite_code_expires_at,
        member_count: memberCount,
      };

      setOrg(orgData);
      setOrgName(orgData.name);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string }, status?: number }, message?: string };
      const msg = err.response?.data?.message || err.message || '未知错误';
      console.error('[CompanySettings] Load failed:', msg, 'orgId:', orgId);
      toast.error(`加载企业信息失败: ${msg}`);
      
      // 如果后端没这个接口，给出更明确的提示
      if (err.response?.status === 404) {
        console.error('[CompanySettings] Endpoint /api/organization/detail not found');
      }
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    loadOrg();
  }, [loadOrg]);

  // Save org name
  const handleSaveName = async () => {
    if (!org || !orgName.trim()) return;
    try {
      setSaving(true);
      const response = await httpClient.put<{ status: number, message?: string }>('/api/organization/detail', { 
        name: orgName.trim() 
      });
      if (response.data?.status !== 200) {
        throw new Error(response.data?.message || '更新失败');
      }
      toast.success('企业名称已更新');
      setOrg(prev => prev ? { ...prev, name: orgName.trim() } : null);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } }, message?: string };
      const msg = error.response?.data?.message || error.message || '更新失败';
      toast.error(`更新企业名称失败: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Regenerate invite code
  const handleRegenerate = async () => {
    if (!org) return;
    try {
      setRegenerating(true);
      const response = await httpClient.post<ApiResponse<{ invite_code: string }>>('/api/organization/invite-code/regenerate');
      const result = response.data;
      if (result.status !== 200) throw new Error(result.message);
      toast.success('邀请码已重新生成');
      setOrg(prev => prev ? { ...prev, invite_code: result.data.invite_code } : null);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string } }, message?: string };
      const msg = err.response?.data?.message || err.message || '未知错误';
      toast.error(`重新生成邀请码失败: ${msg}`);
    } finally {
      setRegenerating(false);
    }
  };

  // Toggle invite code enabled
  const handleToggleInvite = async (enabled: boolean) => {
    if (!org) return;
    try {
      const response = await httpClient.post<ApiResponse<{ enabled: boolean }>>('/api/organization/invite-code/toggle', { enabled });
      const result = response.data;
      if (result.status !== 200) throw new Error(result.message);
      setOrg(prev => prev ? { ...prev, invite_code_enabled: result.data.enabled } : null);
      toast.success(result.data.enabled ? '邀请码已启用' : '邀请码已禁用');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } }, message?: string };
      const msg = error.response?.data?.message || error.message || '操作失败';
      toast.error(`操作失败: ${msg}`);
    }
  };

  // Copy invite code
  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success('邀请码已复制到剪贴板');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('复制失败，请手动复制');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!org) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <Building2 className="w-12 h-12 mb-4 opacity-50" />
        <p>未找到企业信息</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto pb-20">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Building2 className="w-7 h-7 text-primary" />
          企业设置
        </h1>
        <p className="text-sm text-muted-foreground">
          管理企业基本信息和员工注册邀请码
        </p>
      </div>

      {/* Company Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">企业信息</CardTitle>
          <CardDescription>修改企业名称等基本信息</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>企业名称</Label>
            <div className="flex gap-2">
              <Input
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="输入企业名称"
                className="flex-1"
              />
              <Button
                onClick={handleSaveName}
                disabled={saving || orgName.trim() === org.name}
                size="sm"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : '保存'}
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Users className="w-4 h-4" />
              <span>{org.member_count ?? 0} 名成员</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Shield className="w-4 h-4" />
              <span>ID: {safeStr(org.slug)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Invite Code Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">员工注册邀请码</CardTitle>
              <CardDescription>
                员工注册时需输入邀请码才能加入您的企业
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Label htmlFor="invite-toggle" className="text-sm text-muted-foreground">
                {org.invite_code_enabled ? '已启用' : '已禁用'}
              </Label>
              <Switch
                id="invite-toggle"
                checked={org.invite_code_enabled}
                onCheckedChange={handleToggleInvite}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {org.invite_code ? (
            <>
              {/* Invite Code Display */}
              <div className="flex items-center gap-3">
                <div className="flex-1 relative">
                  <code className="block w-full text-center text-2xl font-mono font-bold tracking-[0.3em] bg-muted/50 border border-border rounded-lg py-4 px-6 select-all">
                    {safeStr(org.invite_code)}
                  </code>
                  {!org.invite_code_enabled && (
                    <div className="absolute inset-0 bg-background/80 rounded-lg flex items-center justify-center">
                      <Badge variant="secondary">邀请码已禁用</Badge>
                    </div>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopy(org.invite_code!)}
                  disabled={!org.invite_code_enabled}
                >
                  {copied ? (
                    <CheckCircle2 className="w-4 h-4 mr-1 text-green-500" />
                  ) : (
                    <Copy className="w-4 h-4 mr-1" />
                  )}
                  {copied ? '已复制' : '复制邀请码'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRegenerate}
                  disabled={regenerating}
                >
                  <RefreshCw className={`w-4 h-4 mr-1 ${regenerating ? 'animate-spin' : ''}`} />
                  重新生成
                </Button>
              </div>

              {/* Expiry Info */}
              {org.invite_code_expires_at && (
                <p className="text-xs text-muted-foreground">
                  过期时间: {new Date(org.invite_code_expires_at).toLocaleString('zh-CN')}
                </p>
              )}
            </>
          ) : (
            <div className="text-center py-6">
              <p className="text-sm text-muted-foreground mb-3">尚未生成邀请码</p>
              <Button onClick={handleRegenerate} disabled={regenerating}>
                <RefreshCw className={`w-4 h-4 mr-1 ${regenerating ? 'animate-spin' : ''}`} />
                生成邀请码
              </Button>
            </div>
          )}

          {/* Help Text */}
          <div className="bg-muted/30 rounded-lg p-3 text-xs text-muted-foreground space-y-1">
            <p>* 将邀请码分享给员工，员工在注册页面输入即可自动加入企业</p>
            <p>* 重新生成邀请码后，旧的邀请码将立即失效</p>
            <p>* 禁用邀请码后，新员工将无法通过邀请码注册加入</p>
          </div>
        </CardContent>
      </Card>
      {/* White-Label Branding Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Palette className="w-5 h-5" />
            品牌白标配置
          </CardTitle>
          <CardDescription>自定义登录页 Logo、主题色、标题等品牌元素</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5"><Image className="w-3.5 h-3.5" /> Logo URL</Label>
              <Input
                value={safeStr(brand.logo_url)}
                onChange={(e) => setBrand({ ...brand, logo_url: e.target.value })}
                placeholder="https://your-cdn.com/logo.png"
              />
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5"><Palette className="w-3.5 h-3.5" /> 主题色</Label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={safeStr(brand.primary_color) || '#3b82f6'}
                  onChange={(e) => setBrand({ ...brand, primary_color: e.target.value })}
                  className="w-10 h-10 rounded-lg border border-border cursor-pointer"
                />
                <Input
                  value={safeStr(brand.primary_color)}
                  onChange={(e) => setBrand({ ...brand, primary_color: e.target.value })}
                  placeholder="#3b82f6"
                  className="flex-1"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5"><Type className="w-3.5 h-3.5" /> 公司名称</Label>
              <Input
                value={safeStr(brand.company_name)}
                onChange={(e) => setBrand({ ...brand, company_name: e.target.value })}
                placeholder="留空则使用企业名称"
              />
            </div>
            <div className="space-y-2">
              <Label>标语</Label>
              <Input
                value={safeStr(brand.tagline)}
                onChange={(e) => setBrand({ ...brand, tagline: e.target.value })}
                placeholder="企业标语/副标题"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>登录页标题</Label>
              <Input
                value={safeStr(brand.login_title)}
                onChange={(e) => setBrand({ ...brand, login_title: e.target.value })}
                placeholder="企业级 AI 中控枢纽"
              />
            </div>
            <div className="space-y-2">
              <Label>登录页副标题</Label>
              <Input
                value={safeStr(brand.login_subtitle)}
                onChange={(e) => setBrand({ ...brand, login_subtitle: e.target.value })}
                placeholder="重塑智能化工作流"
              />
            </div>
          </div>

          <div className="flex justify-end">
            <Button onClick={handleSaveBrand} disabled={savingBrand} size="sm">
              {savingBrand ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
              保存品牌配置
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Help Text */}
      <div className="bg-muted/30 rounded-lg p-3 text-xs text-muted-foreground space-y-1">
        <p>* 品牌配置将应用到登录页等面向用户的界面</p>
        <p>* Logo URL 需为可公开访问的图片链接</p>
        <p>* 主题色支持 HEX 格式，如 #3b82f6</p>
      </div>
    </div>
  );
}

export default CompanySettingsPage;

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
} from 'lucide-react';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

interface OrgInfo {
  id: string;
  name: string;
  slug: string;
  invite_code: string | null;
  invite_code_enabled: boolean;
  invite_code_expires_at: string | null;
  member_count?: number;
}

function CompanySettingsPage() {
  const { profile } = useAuth();
  const [org, setOrg] = useState<OrgInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [orgName, setOrgName] = useState('');

  const orgId = (profile as unknown as Record<string, unknown>)?.organization_id as string | undefined;

  // Load organization data
  const loadOrg = useCallback(async () => {
    if (!orgId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);

      // Select only known base columns to avoid issues with missing invite_code columns
      const { data, error } = await supabase
        .from('organizations')
        .select('id, name, slug, created_at, updated_at')
        .eq('id', orgId)
        .single();

      if (error) throw error;

      // Try to get invite_code fields separately (may not exist if migration not run)
      let inviteCode: string | null = null;
      let inviteEnabled = true;
      let inviteExpires: string | null = null;
      try {
        const { data: fullData } = await supabase
          .from('organizations')
          .select('*')
          .eq('id', orgId)
          .single();
        if (fullData) {
          const fd = fullData as Record<string, unknown>;
          inviteCode = (fd.invite_code as string) ?? null;
          inviteEnabled = (fd.invite_code_enabled as boolean) ?? true;
          inviteExpires = (fd.invite_code_expires_at as string) ?? null;
        }
      } catch {
        // invite_code columns may not exist yet — that's OK
      }

      // Get member count
      const { count } = await supabase
        .from('users')
        .select('id', { count: 'exact', head: true })
        .eq('organization_id', orgId);

      const orgData: OrgInfo = {
        id: data.id,
        name: data.name,
        slug: data.slug,
        invite_code: inviteCode,
        invite_code_enabled: inviteEnabled,
        invite_code_expires_at: inviteExpires,
        member_count: count ?? 0,
      };

      setOrg(orgData);
      setOrgName(orgData.name);
    } catch (e) {
      const msg = e instanceof Error ? e.message
        : (e && typeof e === 'object' && 'message' in e) ? String((e as { message: unknown }).message)
        : '未知错误';
      console.error('[CompanySettings] Load failed:', msg, 'orgId:', orgId, 'error:', e);
      toast.error(`加载企业信息失败: ${msg}`);
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
      const { error } = await supabase
        .from('organizations')
        .update({ name: orgName.trim(), updated_at: new Date().toISOString() })
        .eq('id', org.id);
      if (error) throw error;
      toast.success('企业名称已更新');
      setOrg(prev => prev ? { ...prev, name: orgName.trim() } : null);
    } catch {
      toast.error('更新企业名称失败');
    } finally {
      setSaving(false);
    }
  };

  // Regenerate invite code
  const handleRegenerate = async () => {
    if (!org) return;
    try {
      setRegenerating(true);
      const { data, error } = await supabase.rpc('regenerate_invite_code', {
        _org_id: org.id,
      });
      if (error) throw error;
      toast.success('邀请码已重新生成');
      setOrg(prev => prev ? { ...prev, invite_code: data as string } : null);
    } catch (e) {
      toast.error(`重新生成邀请码失败: ${e instanceof Error ? e.message : '未知错误'}`);
    } finally {
      setRegenerating(false);
    }
  };

  // Toggle invite code enabled
  const handleToggleInvite = async (enabled: boolean) => {
    if (!org) return;
    try {
      const { error } = await supabase.rpc('toggle_invite_code', {
        _org_id: org.id,
        _enabled: enabled,
      });
      if (error) throw error;
      setOrg(prev => prev ? { ...prev, invite_code_enabled: enabled } : null);
      toast.success(enabled ? '邀请码已启用' : '邀请码已禁用');
    } catch {
      toast.error('操作失败');
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
              <span>ID: {org.slug}</span>
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
                    {org.invite_code}
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
    </div>
  );
}

export default CompanySettingsPage;

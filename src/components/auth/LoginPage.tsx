import React, { useState, useEffect } from 'react';
import { useAuth } from './AuthContext';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Activity,
  ArrowLeft,
  Briefcase,
  Database,
  FileCheck2,
  KeyRound,
  Loader2,
  LockKeyhole,
  LogIn,
  Mail,
  Radar,
  ShieldCheck,
  Ticket,
  UserPlus,
  Users,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { supabase } from '@/integrations/supabase/client';
import { httpClient } from '@/lib/httpClient';
import './LoginPage.css';

type AppRole = 'boss' | 'employee';

interface BrandConfig {
  logo_url?: string;
  primary_color?: string;
  company_name?: string;
  tagline?: string;
  login_title?: string;
  login_subtitle?: string;
  feature_cards?: { icon?: string; title?: string; desc?: string }[];
}

export function LoginPage() {
  const [brand, setBrand] = useState<BrandConfig>({});

  // Load org brand config (public, no auth required)
  useEffect(() => {
    httpClient.get<{ status: number; data?: BrandConfig }>('/api/organization/brand')
      .then((res) => {
        if (res.data?.data) setBrand(res.data.data);
      })
      .catch(() => { /* brand is optional */ });
  }, []);

  // Derived brand values with defaults
  const brandName = brand.company_name || 'Project Nexus';
  const brandInitial = brandName.charAt(0).toUpperCase();
  const brandTitle = brand.login_title || '科学仪器企业的 AI 增长作战室';
  const brandSubtitle = brand.login_subtitle || '从商机到方案交付，持续推进每一步';
  const brandTagline = brand.tagline || '面向光谱、色谱、质谱、能谱与电子仪器团队，把客户信号、企业知识、方案标书和业务行动汇入同一条可信工作流。';
  const loginStyle = brand.primary_color
    ? ({ '--login-accent': brand.primary_color } as React.CSSProperties)
    : undefined;

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [selectedRole, setSelectedRole] = useState<AppRole>('employee');
  const [inviteCode, setInviteCode] = useState('');
  const [inviteValidating, setInviteValidating] = useState(false);
  const [inviteError, setInviteError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmailSent, setResetEmailSent] = useState(false);
  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    const { error } = await signIn(email, password);

    if (error) {
      toast.error('登录失败', { description: error.message });
    } else {
      toast.success('登录成功', { description: '欢迎回来！' });
      navigate('/');
    }
    setLoading(false);
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();

    // Frontend Validation
    if (password.length < 6) {
      toast.error('密码太短', { description: '密码长度至少为6位' });
      return;
    }

    // Validate invite code for employees
    if (selectedRole === 'employee') {
      if (!inviteCode.trim()) {
        setInviteError('员工注册需要输入企业邀请码');
        return;
      }

      setInviteValidating(true);
      setInviteError('');
      try {
        // @ts-expect-error Supabase types might not be synchronized yet for new RPCs
        const { data: orgId, error } = await supabase.rpc('validate_invite_code', {
          _code: inviteCode.trim(),
        });
        if (error || !orgId) {
          setInviteError('邀请码无效或已过期');
          setInviteValidating(false);
          return;
        }
      } catch {
        setInviteError('验证邀请码失败，请稍后重试');
        setInviteValidating(false);
        return;
      }
      setInviteValidating(false);
    }

    setLoading(true);

    const { error } = await signUp(
      email,
      password,
      name,
      selectedRole,
      selectedRole === 'employee' ? inviteCode.trim() : undefined,
    );

    if (error) {
      toast.error('注册失败', { description: error.message });
    } else {
      toast.success('注册成功', { description: '正在为您自动登录...' });

      // Auto-login after successful registration
      const { error: signInError } = await signIn(email, password);
      if (signInError) {
        toast.error('自动登录失败', { description: '请手动登录' });
      } else {
        navigate('/');
      }
    }
    setLoading(false);
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim()) {
      toast.error('请输入邮箱', { description: '我们需要您的邮箱地址来发送重置链接' });
      return;
    }

    setLoading(true);

    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });

    if (error) {
      toast.error('发送失败', { description: error.message });
    } else {
      setResetEmailSent(true);
      toast.success('邮件已发送', { description: '请检查您的邮箱，点击链接重置密码' });
    }
    setLoading(false);
  };

  // 渲染表单交互区域
  const renderAuthContent = () => {
    if (showForgotPassword) {
      return (
        <div className="login-auth-card login-auth-card--reset relative overflow-hidden p-7 sm:p-9">
          <div className="text-center mb-8 relative z-10">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-md border bg-muted/40">
              <KeyRound className="h-5 w-5 text-primary" />
            </div>
            <h2 className="text-2xl font-bold text-foreground">重置密码</h2>
            <p className="text-muted-foreground mt-2">
              {resetEmailSent ? '重置链接已发送' : '输入您的邮箱地址'}
            </p>
          </div>

          {resetEmailSent ? (
            <div className="text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-success/20 mx-auto flex items-center justify-center">
                <Mail className="w-8 h-8 text-success" />
              </div>
              <div>
                <p className="text-foreground font-medium">邮件已发送到</p>
                <p className="text-primary font-medium mt-1">{email}</p>
              </div>
              <p className="text-sm text-muted-foreground">
                请检查您的邮箱（包括垃圾邮件文件夹），点击邮件中的链接重置密码。
              </p>
              <Button
                variant="outline"
                className="w-full mt-4 h-11 rounded-xl"
                onClick={() => {
                  setShowForgotPassword(false);
                  setResetEmailSent(false);
                }}
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                返回登录
              </Button>
            </div>
          ) : (
            <form onSubmit={handleForgotPassword} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="reset-email">邮箱地址</Label>
                <Input
                  id="reset-email"
                  type="email"
                  placeholder="your@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="h-11 rounded-xl bg-background/60 border-white/20 dark:border-white/10 hover:bg-background/70 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
                />
              </div>
              <Button
                type="submit"
                className="w-full h-11 rounded-xl shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 transition-all"
                disabled={loading}
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Mail className="w-4 h-4 mr-2" />
                )}
                发送重置链接
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="w-full rounded-xl"
                onClick={() => setShowForgotPassword(false)}
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                返回登录
              </Button>
            </form>
          )}
        </div>
      );
    }

    // Default Login/Register Tabs
    return (
      <div className="login-auth-card relative overflow-hidden p-7 sm:p-9">
        <Tabs defaultValue="login" className="space-y-8 relative z-10">
          <TabsList className="login-auth-tabs grid h-10 w-full grid-cols-2">
            <TabsTrigger value="login" className="flex items-center gap-2 text-sm font-medium">
              <LogIn className="w-4 h-4" />
              立即登录
            </TabsTrigger>
            <TabsTrigger value="register" className="flex items-center gap-2 text-sm font-medium">
              <UserPlus className="w-4 h-4" />
              注册账号
            </TabsTrigger>
          </TabsList>

          <TabsContent value="login" className="mt-0 outline-none">
            <form onSubmit={handleSignIn} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="login-email">企业邮箱</Label>
                <Input
                  id="login-email"
                  type="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="h-11 rounded-xl bg-background/60 border-white/20 dark:border-white/10 hover:bg-background/70 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
                  data-testid="login-email-input"
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="login-password">安全密码</Label>
                  <button
                    type="button"
                    onClick={() => setShowForgotPassword(true)}
                    className="text-xs text-primary font-medium hover:underline transition-all"
                  >
                    忘记密码？
                  </button>
                </div>
                <Input
                  id="login-password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-11 rounded-xl bg-background/60 border-white/20 dark:border-white/10 hover:bg-background/70 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
                  data-testid="login-password-input"
                />
              </div>
              <Button
                type="submit"
                className="w-full h-11 rounded-xl font-medium shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 transition-all active:scale-[0.98] mt-2"
                disabled={loading}
                data-testid="login-submit-btn"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <LogIn className="w-4 h-4 mr-2" />
                )}
                登 录 系 统
              </Button>
            </form>
          </TabsContent>

          <TabsContent value="register" className="mt-0 outline-none">
            <form onSubmit={handleSignUp} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="reg-name">真实姓名</Label>
                <Input
                  id="reg-name"
                  type="text"
                  placeholder="您的姓名"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="h-11 rounded-xl bg-background/60 border-white/20 dark:border-white/10 hover:bg-background/70 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
                  data-testid="register-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reg-email">企业邮箱</Label>
                <Input
                  id="reg-email"
                  type="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="h-11 rounded-xl bg-background/60 border-white/20 dark:border-white/10 hover:bg-background/70 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
                  data-testid="register-email-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="reg-password">安全密码</Label>
                <Input
                  id="reg-password"
                  type="password"
                  placeholder="至少 6 位安全密码"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="h-11 rounded-xl bg-background/60 border-white/20 dark:border-white/10 hover:bg-background/70 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
                  data-testid="register-password-input"
                />
              </div>

              {/* Role Selection */}
              <div className="space-y-3 pt-2">
                <Label className="text-sm font-medium">赋予您的系统身份</Label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setSelectedRole('employee')}
                    aria-pressed={selectedRole === 'employee'}
                    className={cn(
                      "flex flex-col items-center gap-3 p-4 rounded-xl border-2 transition-all relative overflow-hidden",
                      selectedRole === 'employee'
                        ? "border-primary bg-primary/5 shadow-sm shadow-primary/10"
                        : "border-border hover:border-primary/40 hover:bg-muted/50"
                    )}
                    data-testid="role-employee-btn"
                  >
                    <div className={cn(
                      "p-2 rounded-full transition-colors",
                      selectedRole === 'employee' ? "bg-primary/10" : "bg-muted"
                    )}>
                      <Users className={cn(
                        "w-5 h-5",
                        selectedRole === 'employee' ? "text-primary" : "text-muted-foreground"
                      )} />
                    </div>
                    <span className={cn(
                      "text-sm font-semibold",
                      selectedRole === 'employee' ? "text-primary" : "text-muted-foreground"
                    )}>
                      全职员工
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedRole('boss')}
                    aria-pressed={selectedRole === 'boss'}
                    className={cn(
                      "flex flex-col items-center gap-3 p-4 rounded-xl border-2 transition-all relative overflow-hidden",
                      selectedRole === 'boss'
                        ? "border-primary bg-primary/5 shadow-sm shadow-primary/10"
                        : "border-border hover:border-primary/40 hover:bg-muted/50"
                    )}
                    data-testid="role-boss-btn"
                  >
                    <div className={cn(
                      "p-2 rounded-full transition-colors",
                      selectedRole === 'boss' ? "bg-primary/10" : "bg-muted"
                    )}>
                      <Briefcase className={cn(
                        "w-5 h-5",
                        selectedRole === 'boss' ? "text-primary" : "text-muted-foreground"
                      )} />
                    </div>
                    <span className={cn(
                      "text-sm font-semibold",
                      selectedRole === 'boss' ? "text-primary" : "text-muted-foreground"
                    )}>
                      企业高管
                    </span>
                  </button>
                </div>
                {selectedRole === 'boss' && (
                  <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 mt-2 animate-in fade-in slide-in-from-top-1">
                    <p className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1.5 leading-snug">
                      <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0" />
                      管理员需超级管理员审批后方可激活后台高级权限
                    </p>
                  </div>
                )}
              </div>

              {/* Invite Code (employees only) */}
              {selectedRole === 'employee' && (
                <div className="space-y-2 pt-2 animate-in fade-in slide-in-from-top-2 flex flex-col">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="reg-invite" className="flex items-center gap-1.5">
                      <Ticket className="w-3.5 h-3.5" />
                      企业邀请码
                    </Label>
                    <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">必填要素</span>
                  </div>
                  <Input
                    id="reg-invite"
                    type="text"
                    placeholder="输入HR提供的6位邀请码"
                    value={inviteCode}
                    onChange={(e) => {
                      setInviteCode(e.target.value);
                      setInviteError('');
                    }}
                    required
                    className={cn("h-11 font-mono tracking-wider text-center uppercase rounded-xl bg-background/50", inviteError && "border-destructive")}
                    data-testid="register-invite-input"
                  />
                  {inviteError && (
                    <p className="text-xs text-destructive flex items-center gap-1 mt-1">
                      <span className="w-1 h-1 rounded-full bg-destructive" />
                      {inviteError}
                    </p>
                  )}
                </div>
              )}

              <Button
                type="submit"
                className="w-full h-11 rounded-xl font-medium shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 transition-all active:scale-[0.98] mt-4"
                disabled={loading}
                data-testid="register-submit-btn"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <UserPlus className="w-4 h-4 mr-2" />
                )}
                立 即 注 册
              </Button>
            </form>
          </TabsContent>
        </Tabs>
      </div>
    );
  };

  return (
    <div className="nexus-login-shell" style={loginStyle}>
      <section className="login-visual-panel" aria-label="Nexus AI Command 产品能力">
        <div className="login-visual-grid" aria-hidden="true" />
        <div className="login-visual-scan" aria-hidden="true" />

        <div className="login-visual-content">
          <header className="login-brand-row">
            <div className="login-brand-lockup">
              {brand.logo_url ? (
                <img src={brand.logo_url} alt={brandName} className="login-brand-logo" />
              ) : (
                <div className="login-brand-logo login-brand-logo--letter" aria-hidden="true">
                  {brandInitial}
                </div>
              )}
              <div>
                <span className="login-brand-name">{brandName}</span>
                <span className="login-brand-kicker">NEXUS AI COMMAND</span>
              </div>
            </div>
            <div className="login-system-status">
              <Activity className="h-4 w-4" />
              <span>AI 作战系统在线</span>
            </div>
          </header>

          <div className="login-hero-copy">
            <p className="login-eyebrow">SCIENTIFIC INSTRUMENT GROWTH OS</p>
            <h1>{brandTitle}</h1>
            <p className="login-hero-subtitle">{brandSubtitle}</p>
            <p className="login-hero-description">{brandTagline}</p>
          </div>

          <div className="login-capability-list">
            {(brand.feature_cards && brand.feature_cards.length > 0
              ? brand.feature_cards
              : [
                  { icon: 'radar', title: '商机雷达', desc: '识别高价值客户信号，排出今天的下一步行动' },
                  { icon: 'file', title: '方案与标书', desc: '基于企业知识生成可引用、可评审的客户方案' },
                  { icon: 'database', title: '知识与证据', desc: '统一产品、竞品与历史项目，回答可追溯' },
                ]
            ).slice(0, 3).map((feature, i) => {
              const iconEl = feature.icon === 'zap' ? <Zap className="h-5 w-5" />
                : feature.icon === 'shield' ? <ShieldCheck className="h-5 w-5" />
                : feature.icon === 'file' ? <FileCheck2 className="h-5 w-5" />
                : feature.icon === 'database' ? <Database className="h-5 w-5" />
                : <Radar className="h-5 w-5" />;
              return (
                <div key={`${feature.title}-${i}`} className="login-capability-item">
                  <div className="login-capability-icon">{iconEl}</div>
                  <div>
                    <h2>{feature.title}</h2>
                    <p>{feature.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="login-product-preview" aria-label="Nexus AI Command 业务作战界面预览">
            <div className="login-preview-toolbar">
              <div className="login-preview-dots" aria-hidden="true"><span /><span /><span /></div>
              <span>今日增长作战室</span>
              <span className="login-preview-live">LIVE</span>
            </div>
            <div className="login-preview-body">
              <img
                src="/login-command-preview.webp"
                alt="Nexus AI Command 商机与行动工作台"
                loading="eager"
                decoding="async"
              />
              <div className="login-preview-signal">
                <Radar className="h-4 w-4" />
                AI 已识别 3 个高价值业务信号
              </div>
            </div>
          </div>

          <footer className="login-trust-rail">
            <span><ShieldCheck className="h-4 w-4" />租户数据隔离</span>
            <span><FileCheck2 className="h-4 w-4" />依据可追溯</span>
            <span><LockKeyhole className="h-4 w-4" />高风险操作确认</span>
          </footer>
        </div>
      </section>

      <section className="login-form-panel" aria-label="账户登录与注册">
        <div className="login-form-grid" aria-hidden="true" />
        <div className="login-form-wrap">
          <div className="login-mobile-brand lg:hidden">
            {brand.logo_url ? (
              <img src={brand.logo_url} alt={brandName} className="login-mobile-logo" />
            ) : (
              <div className="login-mobile-logo login-brand-logo--letter" aria-hidden="true">{brandInitial}</div>
            )}
            <div>
              <h1>{brandName}</h1>
              <p>{brandSubtitle}</p>
            </div>
          </div>

          <div className="login-form-heading hidden lg:block">
            <p>SECURE WORKSPACE</p>
            <h2>欢迎回来</h2>
            <span>登录后继续推进今天的商机、方案与交付任务。</span>
          </div>

          {renderAuthContent()}

          <div className="login-security-note">
            <ShieldCheck className="h-4 w-4" />
            <span>{brandName} 使用企业级加密与租户隔离保护您的数据</span>
          </div>

          <div className="login-legal-links">
            <span>© 2026 {brandName}</span>
            <a href="#">隐私政策</a>
            <a href="#">服务协议</a>
          </div>
        </div>
      </section>
    </div>
  );
}


import React, { useState } from 'react';
import { useAuth } from './AuthContext';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { LogIn, UserPlus, Loader2, Briefcase, Users, KeyRound, ArrowLeft, Mail, Ticket, Sparkles, ShieldCheck, Zap } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { supabase } from '@/integrations/supabase/client';

type AppRole = 'boss' | 'employee';

export function LoginPage() {
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
        <div className="bg-white/60 dark:bg-black/40 backdrop-blur-3xl rounded-3xl border border-white/50 dark:border-white/10 shadow-[0_8px_32px_0_rgba(31,38,135,0.1)] dark:shadow-[0_8px_32px_0_rgba(0,0,0,0.4)] p-8 sm:p-10 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-white/40 to-white/0 dark:from-white/5 dark:to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
          <div className="text-center mb-8 relative z-10">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-700 mx-auto flex items-center justify-center mb-4 shadow-lg shadow-blue-500/20">
              <KeyRound className="w-8 h-8 text-white" />
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
                  className="h-11 rounded-xl bg-background/40 backdrop-blur-sm border-white/20 dark:border-white/10 hover:bg-background/60 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
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
      <div className="bg-white/60 dark:bg-black/40 backdrop-blur-3xl rounded-3xl border border-white/50 dark:border-white/10 shadow-[0_8px_32px_0_rgba(31,38,135,0.1)] dark:shadow-[0_8px_32px_0_rgba(0,0,0,0.4)] p-8 sm:p-10 relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-white/40 to-white/0 dark:from-white/5 dark:to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
        <Tabs defaultValue="login" className="space-y-8 relative z-10">
          <TabsList className="grid w-full grid-cols-2 rounded-xl h-12 p-1 bg-muted/50 backdrop-blur-md">
            <TabsTrigger value="login" className="flex items-center gap-2 rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all text-sm font-medium">
              <LogIn className="w-4 h-4" />
              立即登录
            </TabsTrigger>
            <TabsTrigger value="register" className="flex items-center gap-2 rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all text-sm font-medium">
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
                  className="h-11 rounded-xl bg-background/40 backdrop-blur-sm border-white/20 dark:border-white/10 hover:bg-background/60 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
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
                  className="h-11 rounded-xl bg-background/40 backdrop-blur-sm border-white/20 dark:border-white/10 hover:bg-background/60 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
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
                  className="h-11 rounded-xl bg-background/40 backdrop-blur-sm border-white/20 dark:border-white/10 hover:bg-background/60 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
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
                  className="h-11 rounded-xl bg-background/40 backdrop-blur-sm border-white/20 dark:border-white/10 hover:bg-background/60 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
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
                  className="h-11 rounded-xl bg-background/40 backdrop-blur-sm border-white/20 dark:border-white/10 hover:bg-background/60 hover:border-primary/50 focus:bg-background/80 transition-all duration-300"
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
    <div className="min-h-screen grid lg:grid-cols-[1.5fr_1fr] bg-background">
      {/* Left Side - Brand Presentation (Hidden on mobile) */}
      <div className="hidden lg:flex flex-col justify-between p-12 bg-zinc-950 text-white relative overflow-hidden">
        {/* Abstract Background Glowing Effects & Patterns */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
          {/* Animated Blob Gradients */}
          <div className="absolute -top-[10%] -left-[5%] w-[80%] h-[80%] rounded-full bg-blue-600/30 blur-[140px] animate-blob mix-blend-screen" />
          <div className="absolute bottom-[0%] -right-[5%] w-[70%] h-[70%] rounded-full bg-purple-600/30 blur-[140px] animate-blob mix-blend-screen" style={{ animationDelay: '2s' }} />
          
          {/* Moving Mesh Grid */}
          <div className="absolute inset-0 opacity-[0.03] dark:opacity-[0.07] animate-mesh-float" 
               style={{ backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
          
          {/* Edge Glow Transition - Blends the center line */}
          <div className="absolute top-0 right-0 w-64 h-full bg-gradient-to-l from-background to-transparent z-10" />
          
          {/* Floating Particles (CSS only) */}
          {[...Array(6)].map((_, i) => (
            <div 
              key={i}
              className="absolute rounded-full bg-white animate-pulse"
              style={{
                width: Math.random() * 3 + 1 + 'px',
                height: Math.random() * 3 + 1 + 'px',
                top: Math.random() * 100 + '%',
                left: Math.random() * 100 + '%',
                opacity: Math.random() * 0.5,
                animationDelay: i * 0.7 + 's',
                animationDuration: 3 + Math.random() * 4 + 's'
              }}
            />
          ))}
        </div>

        <div className="relative z-10 flex flex-col gap-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/30 border border-white/10">
              <span className="text-xl font-bold font-sans">N</span>
            </div>
            <span className="text-xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-zinc-100 to-zinc-400">
              Project Nexus
            </span>
          </div>
          
          <div className="mt-8">
            <h1 className="text-4xl lg:text-5xl font-extrabold tracking-tight mb-6 leading-[1.15]">
              企业级 AI 中控枢纽
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 inline-block mt-2">
                重塑智能化工作流
              </span>
            </h1>
            <p className="text-zinc-400 text-lg max-w-md leading-relaxed font-light">
              消除数据孤岛，赋能业务创新。基于先进的大模型架构，为您提供全天候的智能协作与决策支持。
            </p>
          </div>

          {/* Feature Highlight List */}
          <div className="mt-10 space-y-4 max-w-sm">
            {[
              { icon: <Sparkles className="w-5 h-5 text-blue-400" />, title: '深层智慧洞察', desc: '秒级解析高维数据，辅助制定战略级决策' },
              { icon: <Zap className="w-5 h-5 text-purple-400" />, title: '工作流自动化', desc: '通过智能 Agent 矩阵，无缝串联日常繁冗任务' },
              { icon: <ShieldCheck className="w-5 h-5 text-emerald-400" />, title: '强隔离安全架构', desc: '租户沙箱级别的私有化安全隔离，保障核心资产无忧' },
            ].map((feature, i) => (
              <div key={i} className="flex items-start gap-4 p-5 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md transition-all duration-500 hover:bg-white/[0.08] hover:border-blue-500/30 hover:-translate-y-1 hover:shadow-[0_20px_40px_-15px_rgba(0,0,0,0.5)] group relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 via-blue-500/5 to-purple-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
                <div className="mt-0.5 bg-white/10 p-3 rounded-xl group-hover:scale-110 group-hover:bg-blue-500/20 transition-all duration-300 relative z-10">
                  {feature.icon}
                </div>
                <div className="relative z-10">
                  <h3 className="font-bold text-zinc-100 text-base tracking-tight group-hover:text-blue-400 transition-colors">{feature.title}</h3>
                  <p className="text-zinc-400 text-sm mt-1.5 leading-relaxed font-light">{feature.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="relative z-10 flex items-center justify-between text-sm text-zinc-500">
          <p>© 2026 Nexus AI. All rights reserved.</p>
          <div className="flex gap-6">
            <a href="#" className="hover:text-zinc-300 transition-colors">隐私政策</a>
            <a href="#" className="hover:text-zinc-300 transition-colors">服务协议</a>
            <a href="#" className="hover:text-zinc-300 transition-colors">系统日志</a>
          </div>
        </div>
      </div>

      {/* Right Side - Auth Forms Container */}
      <div className="flex items-center justify-center p-6 sm:p-12 relative overflow-hidden bg-background">
        {/* High-end ambient mesh gradient behind the form */}
        <div className="absolute top-0 right-0 w-full h-full overflow-hidden pointer-events-none z-0">
           <div className="absolute top-[-10%] right-[-5%] w-[50%] h-[50%] rounded-full bg-blue-500/10 dark:bg-blue-500/5 blur-[100px] animate-blob mix-blend-multiply dark:mix-blend-screen" />
           <div className="absolute bottom-[-10%] left-[-10%] w-[60%] h-[60%] rounded-full bg-purple-500/10 dark:bg-purple-500/5 blur-[120px] animate-blob mix-blend-multiply dark:mix-blend-screen" style={{ animationDelay: '3s' }} />
           <div className="absolute top-[40%] left-[20%] w-[40%] h-[40%] rounded-full bg-emerald-500/5 dark:bg-emerald-500/5 blur-[100px] animate-blob mix-blend-multiply dark:mix-blend-screen" style={{ animationDelay: '5s' }} />
        </div>

        <div className="w-full max-w-md space-y-8 relative z-10 animate-in fade-in slide-in-from-bottom-8 duration-700 ease-out fill-mode-both">
          
          {/* Mobile Logo Only (Hidden on Desktop) */}
          <div className="lg:hidden text-center mb-8">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-blue-600 mx-auto flex items-center justify-center mb-5 shadow-xl shadow-primary/20">
              <span className="text-3xl font-bold text-white">N</span>
            </div>
            <h1 className="text-3xl font-extrabold text-foreground tracking-tight">Project Nexus</h1>
            <p className="text-muted-foreground mt-2 font-medium">企业智能中控台</p>
          </div>
          
          {renderAuthContent()}
          
          <div className="text-center pt-2 animate-in fade-in slide-in-from-bottom-4 delay-500">
             <p className="text-xs text-muted-foreground/60">
               Nexus AI 采用最高等级数据加密协议保障您的安全
             </p>
          </div>
        </div>
      </div>
    </div>
  );
}


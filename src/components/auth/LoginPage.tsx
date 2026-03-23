import React, { useState } from 'react';
import { useAuth } from './AuthContext';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { LogIn, UserPlus, Loader2, Briefcase, Users, KeyRound, ArrowLeft, Mail, Ticket } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
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
  const { toast } = useToast();

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    const { error } = await signIn(email, password);

    if (error) {
      toast({
        title: '登录失败',
        description: error.message,
        variant: 'destructive',
      });
    } else {
      toast({
        title: '登录成功',
        description: '欢迎回来！',
      });
      navigate('/');
    }
    setLoading(false);
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();

    // Frontend Validation
    if (password.length < 6) {
      toast({
        title: '密码太短',
        description: '密码长度至少为6位',
        variant: 'destructive',
      });
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
      toast({
        title: '注册失败',
        description: error.message,
        variant: 'destructive',
      });
    } else {
      toast({
        title: '注册成功',
        description: '正在为您自动登录...',
      });

      // Auto-login after successful registration
      const { error: signInError } = await signIn(email, password);
      if (signInError) {
        toast({
          title: '自动登录失败',
          description: '请手动登录',
          variant: 'destructive',
        });
      } else {
        navigate('/');
      }
    }
    setLoading(false);
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim()) {
      toast({
        title: '请输入邮箱',
        description: '我们需要您的邮箱地址来发送重置链接',
        variant: 'destructive',
      });
      return;
    }

    setLoading(true);

    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });

    if (error) {
      toast({
        title: '发送失败',
        description: error.message,
        variant: 'destructive',
      });
    } else {
      setResetEmailSent(true);
      toast({
        title: '邮件已发送',
        description: '请检查您的邮箱，点击链接重置密码',
      });
    }
    setLoading(false);
  };

  // Forgot Password View
  if (showForgotPassword) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          {/* Logo & Title */}
          <div className="text-center mb-8">
            <div className="w-16 h-16 rounded-2xl bg-gradient-primary mx-auto flex items-center justify-center mb-4 glow-primary">
              <KeyRound className="w-8 h-8 text-primary-foreground" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">重置密码</h1>
            <p className="text-muted-foreground mt-2">
              {resetEmailSent ? '重置链接已发送' : '输入您的邮箱地址'}
            </p>
          </div>

          {/* Reset Card */}
          <div className="bg-card rounded-2xl border border-border p-6 sm:p-8">
            {resetEmailSent ? (
              <div className="text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-success/20 mx-auto flex items-center justify-center">
                  <Mail className="w-8 h-8 text-success" />
                </div>
                <div>
                  <p className="text-foreground font-medium">邮件已发送到</p>
                  <p className="text-primary">{email}</p>
                </div>
                <p className="text-sm text-muted-foreground">
                  请检查您的邮箱（包括垃圾邮件文件夹），点击邮件中的链接重置密码。
                </p>
                <Button
                  variant="outline"
                  className="w-full mt-4"
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
              <form onSubmit={handleForgotPassword} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="reset-email">邮箱地址</Label>
                  <Input
                    id="reset-email"
                    type="email"
                    placeholder="your@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="h-11"
                  />
                </div>
                <Button
                  type="submit"
                  className="w-full h-11"
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
                  className="w-full"
                  onClick={() => setShowForgotPassword(false)}
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  返回登录
                </Button>
              </form>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo & Title */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-primary mx-auto flex items-center justify-center mb-4 glow-primary">
            <span className="text-3xl font-bold text-primary-foreground">N</span>
          </div>
          <h1 className="text-2xl font-bold text-foreground">Project Nexus</h1>
          <p className="text-muted-foreground mt-2">AI 驱动的企业中控台</p>
        </div>

        {/* Auth Card */}
        <div className="bg-card rounded-2xl border border-border p-6 sm:p-8">
          <Tabs defaultValue="login" className="space-y-6">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login" className="flex items-center gap-2">
                <LogIn className="w-4 h-4" />
                登录
              </TabsTrigger>
              <TabsTrigger value="register" className="flex items-center gap-2">
                <UserPlus className="w-4 h-4" />
                注册
              </TabsTrigger>
            </TabsList>

            <TabsContent value="login">
              <form onSubmit={handleSignIn} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="login-email">邮箱</Label>
                  <Input
                    id="login-email"
                    type="email"
                    placeholder="your@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="h-11"
                    data-testid="login-email-input"
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="login-password">密码</Label>
                    <button
                      type="button"
                      onClick={() => setShowForgotPassword(true)}
                      className="text-xs text-primary hover:underline"
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
                    className="h-11"
                    data-testid="login-password-input"
                  />
                </div>
                <Button
                  type="submit"
                  className="w-full h-11"
                  disabled={loading}
                  data-testid="login-submit-btn"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <LogIn className="w-4 h-4 mr-2" />
                  )}
                  登录
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="register">
              <form onSubmit={handleSignUp} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="reg-name">姓名</Label>
                  <Input
                    id="reg-name"
                    type="text"
                    placeholder="您的姓名"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="h-11"
                    data-testid="register-name-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="reg-email">邮箱</Label>
                  <Input
                    id="reg-email"
                    type="email"
                    placeholder="your@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="h-11"
                    data-testid="register-email-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="reg-password">密码</Label>
                  <Input
                    id="reg-password"
                    type="password"
                    placeholder="至少6位密码"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    className="h-11"
                    data-testid="register-password-input"
                  />
                </div>

                {/* Role Selection */}
                <div className="space-y-2">
                  <Label>角色</Label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setSelectedRole('employee')}
                      className={cn(
                        "flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all",
                        selectedRole === 'employee'
                          ? "border-primary bg-primary/10"
                          : "border-border hover:border-primary/50"
                      )}
                      data-testid="role-employee-btn"
                    >
                      <Users className={cn(
                        "w-6 h-6",
                        selectedRole === 'employee' ? "text-primary" : "text-muted-foreground"
                      )} />
                      <span className={cn(
                        "text-sm font-medium",
                        selectedRole === 'employee' ? "text-primary" : "text-muted-foreground"
                      )}>
                        员工
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedRole('boss')}
                      className={cn(
                        "flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all",
                        selectedRole === 'boss'
                          ? "border-primary bg-primary/10"
                          : "border-border hover:border-primary/50"
                      )}
                      data-testid="role-boss-btn"
                    >
                      <Briefcase className={cn(
                        "w-6 h-6",
                        selectedRole === 'boss' ? "text-primary" : "text-muted-foreground"
                      )} />
                      <span className={cn(
                        "text-sm font-medium",
                        selectedRole === 'boss' ? "text-primary" : "text-muted-foreground"
                      )}>
                        老板
                      </span>
                    </button>
                  </div>
                  {selectedRole === 'boss' && (
                    <p className="text-xs text-amber-600 dark:text-amber-400">
                      管理员账号注册后需要超级管理员审批通过才能使用管理功能
                    </p>
                  )}
                </div>

                {/* Invite Code (employees only) */}
                {selectedRole === 'employee' && (
                  <div className="space-y-2">
                    <Label htmlFor="reg-invite">
                      <span className="flex items-center gap-1.5">
                        <Ticket className="w-3.5 h-3.5" />
                        企业邀请码
                      </span>
                    </Label>
                    <Input
                      id="reg-invite"
                      type="text"
                      placeholder="请输入企业邀请码"
                      value={inviteCode}
                      onChange={(e) => {
                        setInviteCode(e.target.value);
                        setInviteError('');
                      }}
                      required
                      className={cn("h-11 font-mono tracking-wider", inviteError && "border-destructive")}
                      data-testid="register-invite-input"
                    />
                    {inviteError && (
                      <p className="text-xs text-destructive">{inviteError}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      请向您的企业管理员获取邀请码
                    </p>
                  </div>
                )}

                <Button
                  type="submit"
                  className="w-full h-11"
                  disabled={loading}
                  data-testid="register-submit-btn"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <UserPlus className="w-4 h-4 mr-2" />
                  )}
                  注册
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </div>

      </div>
    </div>
  );
}

import React, { useState } from 'react';
import { useAuth } from './AuthContext';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { LogIn, UserPlus, Loader2, Briefcase, Users } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

type AppRole = 'boss' | 'employee';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [selectedRole, setSelectedRole] = useState<AppRole>('employee');
  const [loading, setLoading] = useState(false);
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
    setLoading(true);
    
    const { error } = await signUp(email, password, name, selectedRole);
    
    if (error) {
      toast({
        title: '注册失败',
        description: error.message,
        variant: 'destructive',
      });
    } else {
      toast({
        title: '注册成功',
        description: '账号已创建，请登录！',
      });
    }
    setLoading(false);
  };

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
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="login-password">密码</Label>
                  <Input
                    id="login-password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
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
                </div>

                <Button
                  type="submit"
                  className="w-full h-11"
                  disabled={loading}
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

        {/* Demo Account Info */}
        <div className="mt-6 p-4 bg-secondary/50 rounded-xl text-center">
          <p className="text-sm text-muted-foreground">
            💡 演示提示：注册后即可登录体验完整功能
          </p>
        </div>
      </div>
    </div>
  );
}

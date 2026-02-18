/**
 * 个人中心页面
 * 展示和管理个人信息、账户设置等
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';

import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import {
  User,
  Mail,
  Phone,
  Shield,
  Bell,
  Lock,
  Camera,
  Award,
  TrendingUp,
  Calendar,
  Save,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import { useUser } from '@/contexts/UserContext';
import { useAuth } from '@/components/auth/AuthContext';
import { toast } from 'sonner';
import { NotificationPreferences } from '@/components/settings/NotificationPreferences';
import { supabase } from '@/integrations/supabase/client';

export function ProfileCenter() {
  const { user } = useUser();
  const { session, refreshProfile } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');
  const [isEditing, setIsEditing] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // 受控表单状态
  const [editName, setEditName] = useState(user.name || '');
  const [editPhone, setEditPhone] = useState('');

  // 当 user 数据变化时同步表单
  useEffect(() => {
    setEditName(user.name || '');
  }, [user.name]);

  // 密码修改状态
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);

  const handleUpdatePassword = async () => {
    // 验证
    if (!currentPassword) {
      toast.error('请输入当前密码');
      return;
    }
    if (newPassword.length < 6) {
      toast.error('新密码至少需要6个字符');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('两次输入的新密码不一致');
      return;
    }
    if (currentPassword === newPassword) {
      toast.error('新密码不能与当前密码相同');
      return;
    }

    setIsUpdatingPassword(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) {
        toast.error(`密码更新失败: ${error.message}`);
      } else {
        toast.success('密码更新成功');
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
      }
    } catch (err) {
      toast.error('密码更新失败，请稍后重试');
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  const userDetails = {
    email: session?.user?.email || '—',
    phone: '—',
    joinDate: '—',
    department: user.department || '—',
    position: '—',
    employeeId: '—',
  };

  const achievements: { name: string; icon: string; date: string; description: string }[] = [];

  const stats = {
    totalProjects: 0,
    completedProjects: 0,
    totalSales: 0,
    thisMonthSales: 0,
    attendanceRate: 0,
    performanceScore: user.score || 0,
  };

  const handleSaveProfile = async () => {
    if (!editName.trim()) {
      toast.error('姓名不能为空');
      return;
    }

    setIsSavingProfile(true);
    try {
      // 直接从 Supabase 获取当前会话，避免 React 闭包问题
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.user) {
        toast.error('未登录，请重新登录');
        return;
      }

      const userId = session.user.id;

      // 直接更新 users 表中的 name 字段
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { error } = await (supabase.from('users') as any)
        .update({ name: editName.trim() })
        .eq('id', userId);

      if (error) {
        console.error('Profile save error:', error);
        toast.error('保存失败: ' + error.message);
        return;
      }

      // 刷新 AuthContext 中的 profile，使侧边栏等全局组件也更新
      await refreshProfile();

      toast.success('个人信息保存成功');
      setIsEditing(false);
    } catch (err) {
      console.error('Profile save exception:', err);
      toast.error('保存失败，请稍后重试');
    } finally {
      setIsSavingProfile(false);
    }
  };

  const getRoleDisplayName = (role: string) => {
    switch (role) {
      case 'boss':
      case 'founder':
        return '企业管理员';
      case 'manager':
        return '部门经理';
      case 'sales':
      case 'employee':
      default:
        return '销售精英';
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold">个人中心</h1>
        <p className="text-muted-foreground">管理您的个人信息和账户设置</p>
      </div>

      {/* 用户概览卡片 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row items-center md:items-start gap-6">
            {/* 头像 */}
            <div className="relative">
              <Avatar className="w-24 h-24">
                <AvatarImage src={user.avatar} alt={user.name} />
                <AvatarFallback className="text-2xl bg-primary text-primary-foreground">
                  {user.name?.[0] || 'U'}
                </AvatarFallback>
              </Avatar>
              <Button
                size="icon"
                variant="secondary"
                className="absolute bottom-0 right-0 rounded-full w-8 h-8"
              >
                <Camera className="w-4 h-4" />
              </Button>
            </div>

            {/* 基本信息 */}
            <div className="flex-1 text-center md:text-left">
              <div className="flex items-center justify-center md:justify-start gap-2 mb-1">
                <h2 className="text-xl font-bold">{user.name}</h2>
                <Badge variant="secondary">{getRoleDisplayName(user.role)}</Badge>
              </div>
              <p className="text-muted-foreground mb-3">{userDetails.department} · {userDetails.position}</p>
              <div className="flex flex-wrap justify-center md:justify-start gap-4 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Mail className="w-4 h-4" />
                  {userDetails.email}
                </span>
                <span className="flex items-center gap-1">
                  <Phone className="w-4 h-4" />
                  {userDetails.phone}
                </span>
                <span className="flex items-center gap-1">
                  <Calendar className="w-4 h-4" />
                  入职: {userDetails.joinDate}
                </span>
              </div>
            </div>

            {/* 绩效得分 */}
            <div className="text-center p-4 bg-primary/5 rounded-xl">
              <div className="text-3xl font-bold text-primary">{stats.performanceScore}</div>
              <p className="text-sm text-muted-foreground">绩效得分</p>
              {stats.performanceScore > 0 && (
                <div className="flex items-center justify-center gap-1 mt-1 text-xs text-green-500">
                  <TrendingUp className="w-3 h-3" />
                  趋势
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="text-2xl font-bold">{stats.totalProjects}</div>
              <p className="text-sm text-muted-foreground">参与项目</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-500">¥{(stats.totalSales / 10000).toFixed(0)}万</div>
              <p className="text-sm text-muted-foreground">累计销售额</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="text-2xl font-bold">{stats.attendanceRate}%</div>
              <p className="text-sm text-muted-foreground">出勤率</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-500">{achievements.length}</div>
              <p className="text-sm text-muted-foreground">获得徽章</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 详细信息标签页 */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="profile" className="gap-2">
            <User className="w-4 h-4" />
            个人信息
          </TabsTrigger>
          <TabsTrigger value="achievements" className="gap-2">
            <Award className="w-4 h-4" />
            成就徽章
          </TabsTrigger>
          <TabsTrigger value="notifications" className="gap-2">
            <Bell className="w-4 h-4" />
            通知设置
          </TabsTrigger>
          <TabsTrigger value="security" className="gap-2">
            <Shield className="w-4 h-4" />
            安全设置
          </TabsTrigger>
        </TabsList>

        {/* 个人信息 */}
        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>个人信息</CardTitle>
                  <CardDescription>查看和编辑您的个人资料</CardDescription>
                </div>
                {isEditing ? (
                  <div className="flex gap-2">
                    <Button variant="outline" onClick={() => { setIsEditing(false); setEditName(user.name || ''); }}>取消</Button>
                    <Button onClick={handleSaveProfile} disabled={isSavingProfile} className="gap-2">
                      {isSavingProfile ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Save className="w-4 h-4" />
                      )}
                      保存
                    </Button>
                  </div>
                ) : (
                  <Button variant="outline" onClick={() => setIsEditing(true)}>编辑</Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label>姓名</Label>
                  <Input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    disabled={!isEditing}
                    placeholder="请输入姓名"
                  />
                </div>
                <div className="space-y-2">
                  <Label>工号</Label>
                  <Input defaultValue={userDetails.employeeId} disabled />
                </div>
                <div className="space-y-2">
                  <Label>邮箱</Label>
                  <Input defaultValue={userDetails.email} disabled={!isEditing} />
                </div>
                <div className="space-y-2">
                  <Label>手机号</Label>
                  <Input defaultValue={userDetails.phone} disabled={!isEditing} />
                </div>
                <div className="space-y-2">
                  <Label>部门</Label>
                  <Input defaultValue={userDetails.department} disabled />
                </div>
                <div className="space-y-2">
                  <Label>职位</Label>
                  <Input defaultValue={userDetails.position} disabled />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 成就徽章 */}
        <TabsContent value="achievements">
          <Card>
            <CardHeader>
              <CardTitle>成就徽章</CardTitle>
              <CardDescription>您获得的所有荣誉徽章</CardDescription>
            </CardHeader>
            <CardContent>
              {achievements.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <p className="text-muted-foreground">暂无成就徽章</p>
                  <p className="text-xs text-muted-foreground mt-1">完成目标任务后将自动获得徽章</p>
                </div>
              ) : (
                <div className="grid md:grid-cols-2 gap-4">
                  {achievements.map((achievement, index) => (
                    <div key={index} className="flex items-center gap-4 p-4 rounded-lg border">
                      <div className="text-4xl">{achievement.icon}</div>
                      <div className="flex-1">
                        <h4 className="font-medium">{achievement.name}</h4>
                        <p className="text-sm text-muted-foreground">{achievement.description}</p>
                        <p className="text-xs text-muted-foreground mt-1">获得时间: {achievement.date}</p>
                      </div>
                      <CheckCircle2 className="w-5 h-5 text-green-500" />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 通知设置 - B12 新增 */}
        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>通知偏好设置</CardTitle>
              <CardDescription>管理您的通知渠道、免打扰时段和通知类型</CardDescription>
            </CardHeader>
            <CardContent>
              <NotificationPreferences />
            </CardContent>
          </Card>
        </TabsContent>

        {/* 安全设置 */}
        <TabsContent value="security">
          <Card>
            <CardHeader>
              <CardTitle>安全设置</CardTitle>
              <CardDescription>管理您的账户安全和通知偏好</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 修改密码 */}
              <div className="space-y-4">
                <h4 className="font-medium flex items-center gap-2">
                  <Lock className="w-4 h-4" />
                  修改密码
                </h4>
                <div className="grid md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>当前密码</Label>
                    <Input
                      type="password"
                      placeholder="请输入当前密码"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>新密码</Label>
                    <Input
                      type="password"
                      placeholder="请输入新密码（至少6位）"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>确认新密码</Label>
                    <Input
                      type="password"
                      placeholder="请再次输入新密码"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                    />
                  </div>
                </div>
                <Button onClick={handleUpdatePassword} disabled={isUpdatingPassword}>
                  {isUpdatingPassword ? '更新中...' : '更新密码'}
                </Button>
              </div>

              <Separator />

              {/* 通知设置 */}
              <div className="space-y-4">
                <h4 className="font-medium flex items-center gap-2">
                  <Bell className="w-4 h-4" />
                  通知设置
                </h4>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">邮件通知</p>
                      <p className="text-sm text-muted-foreground">接收重要事项的邮件提醒</p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">审批提醒</p>
                      <p className="text-sm text-muted-foreground">审批状态变更时通知我</p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">任务提醒</p>
                      <p className="text-sm text-muted-foreground">任务到期前提醒我</p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">AI助手消息</p>
                      <p className="text-sm text-muted-foreground">接收AI助手的主动推送</p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default ProfileCenter;
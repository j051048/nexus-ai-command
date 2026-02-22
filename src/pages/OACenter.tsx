import { useState, useEffect, useCallback } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  CalendarDays,
  Video,
  ListTodo,
  Plus,
  Loader2,
  Clock,
  CheckCircle2,
  XCircle,
  CalendarOff,
  ClipboardList,
  FileText,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';

// Local interfaces for tables not in types.ts
interface LeaveRequest {
  id: string;
  user_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: string;
  approver_id?: string;
  organization_id?: string;
  created_at: string;
}

interface MeetingBooking {
  id: string;
  title: string;
  room_id?: string;
  organizer_id: string;
  start_time: string;
  end_time: string;
  attendees?: string[];
  status: string;
  organization_id?: string;
  created_at: string;
}

interface OATask {
  id: string;
  organization_id: string;
  title: string;
  description: string | null;
  status: string;
  priority: string;
  assignee_id: string | null;
  due_date: string | null;
  created_at: string;
}

export function OACenter() {
  const { user, profile } = useAuth();
  const [activeTab, setActiveTab] = useState('leave');

  // --- Leave tab ---
  const [leaves, setLeaves] = useState<LeaveRequest[]>([]);
  const [leaveLoading, setLeaveLoading] = useState(true);
  const [leaveDialogOpen, setLeaveDialogOpen] = useState(false);
  const [leaveSubmitting, setLeaveSubmitting] = useState(false);
  const [leaveForm, setLeaveForm] = useState({
    leave_type: 'annual',
    start_date: '',
    end_date: '',
    reason: '',
  });

  const fetchLeaves = useCallback(async () => {
    try {
      if (!user?.id) return;
      const { data, error } = await (supabase.from('oa_leave_requests') as any)
        .select('*')
        .eq('user_id', user.id)
        .order('created_at', { ascending: false });
      if (error) throw error;
      setLeaves((data as LeaveRequest[]) || []);
    } catch (error: any) {
      console.error('Error fetching leaves:', error);
    } finally {
      setLeaveLoading(false);
    }
  }, [user?.id]);

  const handleSubmitLeave = async () => {
    if (!leaveForm.start_date || !leaveForm.end_date) {
      toast.error('请选择起止日期');
      return;
    }
    if (!leaveForm.reason.trim()) {
      toast.error('请填写请假事由');
      return;
    }
    setLeaveSubmitting(true);
    try {
      const start = new Date(leaveForm.start_date);
      const end = new Date(leaveForm.end_date);
      const days = Math.max(1, Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1);

      const { error } = await (supabase.from('oa_leave_requests') as any).insert({
        user_id: user?.id,
        organization_id: profile?.organization_id,
        leave_type: leaveForm.leave_type,
        start_date: leaveForm.start_date,
        end_date: leaveForm.end_date,
        days,
        reason: leaveForm.reason,
        status: days <= 1 ? 'approved' : 'pending',
      });
      if (error) throw error;
      toast.success(days <= 1 ? '1天以内自动审批通过' : '请假申请已提交，等待审批');
      setLeaveDialogOpen(false);
      setLeaveForm({ leave_type: 'annual', start_date: '', end_date: '', reason: '' });
      fetchLeaves();
    } catch (error: any) {
      toast.error(error?.message || '提交失败');
    } finally {
      setLeaveSubmitting(false);
    }
  };

  // --- Meeting tab ---
  const [meetings, setMeetings] = useState<MeetingBooking[]>([]);
  const [meetingLoading, setMeetingLoading] = useState(true);
  const [meetingDialogOpen, setMeetingDialogOpen] = useState(false);
  const [meetingSubmitting, setMeetingSubmitting] = useState(false);
  const [meetingForm, setMeetingForm] = useState({
    title: '',
    start_time: '',
    end_time: '',
  });

  const fetchMeetings = useCallback(async () => {
    try {
      if (!profile?.organization_id) return;
      const { data, error } = await (supabase.from('oa_meeting_bookings') as any)
        .select('*')
        .eq('organization_id', profile.organization_id)
        .order('start_time', { ascending: false })
        .limit(50);
      if (error) throw error;
      setMeetings((data as MeetingBooking[]) || []);
    } catch (error: any) {
      console.error('Error fetching meetings:', error);
    } finally {
      setMeetingLoading(false);
    }
  }, [profile?.organization_id]);

  const handleSubmitMeeting = async () => {
    if (!meetingForm.title.trim()) {
      toast.error('请填写会议主题');
      return;
    }
    if (!meetingForm.start_time || !meetingForm.end_time) {
      toast.error('请选择会议时间');
      return;
    }
    setMeetingSubmitting(true);
    try {
      const { error } = await (supabase.from('oa_meeting_bookings') as any).insert({
        title: meetingForm.title,
        organizer_id: user?.id,
        organization_id: profile?.organization_id,
        start_time: meetingForm.start_time,
        end_time: meetingForm.end_time,
        status: 'confirmed',
      });
      if (error) throw error;
      toast.success('会议已预约');
      setMeetingDialogOpen(false);
      setMeetingForm({ title: '', start_time: '', end_time: '' });
      fetchMeetings();
    } catch (error: any) {
      toast.error(error?.message || '预约失败');
    } finally {
      setMeetingSubmitting(false);
    }
  };

  // --- Task tab ---
  const [tasks, setTasks] = useState<OATask[]>([]);
  const [taskLoading, setTaskLoading] = useState(true);
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);
  const [taskSubmitting, setTaskSubmitting] = useState(false);
  const [taskFilter, setTaskFilter] = useState('all');
  const [taskForm, setTaskForm] = useState({
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
  });

  const fetchTasks = useCallback(async () => {
    try {
      if (!profile?.organization_id) return;
      let query = supabase
        .from('oa_tasks')
        .select('*')
        .eq('organization_id', profile.organization_id)
        .order('created_at', { ascending: false });

      // Show tasks assigned to the user, or created by them
      if (user?.id) {
        query = query.or(`assignee_id.eq.${user.id}`);
      }

      const { data, error } = await query;
      if (error) throw error;
      setTasks((data as OATask[]) || []);
    } catch (error: any) {
      console.error('Error fetching tasks:', error);
    } finally {
      setTaskLoading(false);
    }
  }, [profile?.organization_id, user?.id]);

  const handleSubmitTask = async () => {
    if (!taskForm.title.trim()) {
      toast.error('请填写任务标题');
      return;
    }
    setTaskSubmitting(true);
    try {
      const { error } = await supabase.from('oa_tasks').insert({
        title: taskForm.title,
        description: taskForm.description || null,
        priority: taskForm.priority,
        due_date: taskForm.due_date || null,
        assignee_id: user?.id,
        organization_id: profile?.organization_id,
        status: 'pending',
      } as any);
      if (error) throw error;
      toast.success('任务已创建');
      setTaskDialogOpen(false);
      setTaskForm({ title: '', description: '', priority: 'medium', due_date: '' });
      fetchTasks();
    } catch (error: any) {
      toast.error(error?.message || '创建失败');
    } finally {
      setTaskSubmitting(false);
    }
  };

  useEffect(() => {
    fetchLeaves();
    fetchMeetings();
    fetchTasks();
  }, [fetchLeaves, fetchMeetings, fetchTasks]);

  const handleCancelLeave = async (leaveId: string) => {
    if (!window.confirm('确认要撤回这条请假申请吗？')) return;
    try {
      const { error } = await (supabase.from('oa_leave_requests') as any)
        .update({ status: 'cancelled' })
        .eq('id', leaveId);
      if (error) throw error;
      toast.success('请假申请已撤回');
      fetchLeaves();
    } catch (error: any) {
      toast.error(error?.message || '撤回失败');
    }
  };

  const handleCancelMeeting = async (meetingId: string) => {
    if (!window.confirm('确认要取消这场会议吗？')) return;
    try {
      const { error } = await (supabase.from('oa_meeting_bookings') as any)
        .update({ status: 'cancelled' })
        .eq('id', meetingId);
      if (error) throw error;
      toast.success('会议已取消');
      fetchMeetings();
    } catch (error: any) {
      toast.error(error?.message || '取消失败');
    }
  };

  const handleChangeTaskStatus = async (taskId: string, newStatus: string) => {
    try {
      const { error } = await supabase
        .from('oa_tasks')
        .update({ status: newStatus } as any)
        .eq('id', taskId);
      if (error) throw error;
      toast.success('任务状态已更新');
      fetchTasks();
    } catch (error: any) {
      toast.error(error?.message || '更新失败');
    }
  };

  const filteredTasks = taskFilter === 'all' ? tasks : tasks.filter((t) => t.status === taskFilter);

  // --- Helpers ---
  const getLeaveTypeName = (type: string) => {
    switch (type) {
      case 'annual': return '年假';
      case 'sick': return '病假';
      case 'personal': return '事假';
      case 'marriage': return '婚假';
      case 'maternity': return '产假';
      case 'bereavement': return '丧假';
      default: return type;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
      case 'confirmed':
      case 'completed':
        return <Badge className="bg-green-500/10 text-green-600 border-green-200">{status === 'completed' ? '已完成' : '已通过'}</Badge>;
      case 'rejected':
      case 'cancelled':
        return <Badge className="bg-red-500/10 text-red-600 border-red-200">{status === 'cancelled' ? '已取消' : '已拒绝'}</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-500/10 text-yellow-600 border-yellow-200">待审批</Badge>;
      case 'in_progress':
        return <Badge className="bg-blue-500/10 text-blue-600 border-blue-200">进行中</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'high':
      case 'urgent':
        return <Badge className="bg-red-500/10 text-red-600 border-red-200">紧急</Badge>;
      case 'medium':
        return <Badge className="bg-yellow-500/10 text-yellow-600 border-yellow-200">中</Badge>;
      case 'low':
        return <Badge className="bg-gray-500/10 text-gray-600 border-gray-200">低</Badge>;
      default:
        return <Badge variant="outline">{priority}</Badge>;
    }
  };

  const leaveStats = {
    total: leaves.length,
    pending: leaves.filter((l) => l.status === 'pending').length,
    totalDays: leaves
      .filter((l) => l.status === 'approved')
      .reduce((sum, l) => sum + (l.days || 0), 0),
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">OA 办公中心</h1>
          <p className="text-muted-foreground">管理请假、会议和任务</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="leave" className="gap-2">
            <CalendarDays className="w-4 h-4" />
            请假管理
          </TabsTrigger>
          <TabsTrigger value="meeting" className="gap-2">
            <Video className="w-4 h-4" />
            会议预约
          </TabsTrigger>
          <TabsTrigger value="task" className="gap-2">
            <ListTodo className="w-4 h-4" />
            任务管理
          </TabsTrigger>
          <TabsTrigger value="report" className="gap-2">
            <FileText className="w-4 h-4" />
            工作报告
          </TabsTrigger>
        </TabsList>

        {/* 请假管理 */}
        <TabsContent value="leave" className="space-y-4">
          {/* 统计卡片 */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">已请假天数</p>
                    <p className="text-2xl font-bold">{leaveStats.totalDays}</p>
                  </div>
                  <div className="p-3 rounded-full bg-blue-500/10">
                    <CalendarDays className="w-6 h-6 text-blue-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">待审批</p>
                    <p className="text-2xl font-bold text-yellow-500">{leaveStats.pending}</p>
                  </div>
                  <div className="p-3 rounded-full bg-yellow-500/10">
                    <Clock className="w-6 h-6 text-yellow-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">总申请数</p>
                    <p className="text-2xl font-bold">{leaveStats.total}</p>
                  </div>
                  <div className="p-3 rounded-full bg-green-500/10">
                    <CheckCircle2 className="w-6 h-6 text-green-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 操作栏 */}
          <div className="flex justify-end">
            <Button onClick={() => setLeaveDialogOpen(true)} className="gap-2">
              <Plus className="w-4 h-4" />
              申请请假
            </Button>
          </div>

          {/* 请假记录 */}
          <Card>
            <CardHeader>
              <CardTitle>请假记录</CardTitle>
              <CardDescription>您的请假申请历史</CardDescription>
            </CardHeader>
            <CardContent>
              {leaveLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : leaves.length === 0 ? (
                <div className="text-center py-12">
                  <CalendarOff className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">暂无请假记录</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {leaves.map((leave) => (
                    <div
                      key={leave.id}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        <div className="text-sm">
                          <p className="font-medium">
                            {getLeaveTypeName(leave.leave_type)} &middot; {leave.days}天
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {leave.start_date} ~ {leave.end_date}
                          </p>
                          {leave.reason && (
                            <p className="text-xs text-muted-foreground mt-1 truncate max-w-md">
                              {leave.reason}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {leave.status === 'pending' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-500 hover:text-red-600 h-7 px-2"
                            onClick={() => handleCancelLeave(leave.id)}
                          >
                            撤回
                          </Button>
                        )}
                        {getStatusBadge(leave.status)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 会议预约 */}
        <TabsContent value="meeting" className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setMeetingDialogOpen(true)} className="gap-2">
              <Plus className="w-4 h-4" />
              预约会议
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>会议列表</CardTitle>
              <CardDescription>组织内的会议预约记录</CardDescription>
            </CardHeader>
            <CardContent>
              {meetingLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : meetings.length === 0 ? (
                <div className="text-center py-12">
                  <Video className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">暂无会议记录</p>
                  <Button
                    variant="outline"
                    className="mt-4"
                    onClick={() => setMeetingDialogOpen(true)}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    预约第一场会议
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {meetings.map((meeting) => (
                    <div
                      key={meeting.id}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        <div className="text-sm">
                          <p className="font-medium">{meeting.title}</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(meeting.start_time).toLocaleString()} ~{' '}
                            {new Date(meeting.end_time).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {meeting.status === 'confirmed' && meeting.organizer_id === user?.id && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-500 hover:text-red-600 h-7 px-2"
                            onClick={() => handleCancelMeeting(meeting.id)}
                          >
                            取消
                          </Button>
                        )}
                        {getStatusBadge(meeting.status)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 任务管理 */}
        <TabsContent value="task" className="space-y-4">
          {/* 筛选栏 + 新建 */}
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              {[
                { value: 'all', label: '全部' },
                { value: 'pending', label: '待办' },
                { value: 'in_progress', label: '进行中' },
                { value: 'completed', label: '已完成' },
              ].map((f) => (
                <Button
                  key={f.value}
                  variant={taskFilter === f.value ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setTaskFilter(f.value)}
                >
                  {f.label}
                </Button>
              ))}
            </div>
            <Button onClick={() => setTaskDialogOpen(true)} className="gap-2">
              <Plus className="w-4 h-4" />
              新建任务
            </Button>
          </div>

          {/* 任务列表 */}
          <Card>
            <CardHeader>
              <CardTitle>任务列表</CardTitle>
              <CardDescription>分配给您的任务</CardDescription>
            </CardHeader>
            <CardContent>
              {taskLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : filteredTasks.length === 0 ? (
                <div className="text-center py-12">
                  <ClipboardList className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">
                    {taskFilter === 'all' ? '暂无任务' : '该状态下暂无任务'}
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredTasks.map((task) => (
                    <div
                      key={task.id}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        <div className="text-sm">
                          <p className="font-medium">{task.title}</p>
                          {task.description && (
                            <p className="text-xs text-muted-foreground truncate max-w-md">
                              {task.description}
                            </p>
                          )}
                          <p className="text-xs text-muted-foreground mt-1">
                            {task.due_date
                              ? `截止: ${new Date(task.due_date).toLocaleDateString()}`
                              : '无截止日期'}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {getPriorityBadge(task.priority)}
                        <Select
                          value={task.status}
                          onValueChange={(v) => handleChangeTaskStatus(task.id, v)}
                        >
                          <SelectTrigger className="w-[100px] h-7 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="pending">待办</SelectItem>
                            <SelectItem value="in_progress">进行中</SelectItem>
                            <SelectItem value="completed">已完成</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 工作报告 */}
        <TabsContent value="report" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>AI 工作报告</CardTitle>
              <CardDescription>自动聚合本周工作数据，AI 帮您撰写周报/日报</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 space-y-4">
                <FileText className="w-12 h-12 text-muted-foreground mx-auto" />
                <p className="text-muted-foreground">
                  在 AI 聊天面板中输入 <span className="font-medium text-primary">"帮我写周报"</span> 或 <span className="font-medium text-primary">"生成日报"</span>，
                  AI 将自动汇总您的任务完成情况、项目进度，生成专业的工作报告。
                </p>
                <div className="flex justify-center gap-3">
                  <Button variant="outline" size="sm" onClick={() => toast.info('请在右侧 AI 聊天面板输入"帮我写日报"')}>
                    <FileText className="w-4 h-4 mr-2" />
                    AI 生成日报
                  </Button>
                  <Button size="sm" onClick={() => toast.info('请在右侧 AI 聊天面板输入"帮我写周报"')}>
                    <FileText className="w-4 h-4 mr-2" />
                    AI 生成周报
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 请假 Dialog */}
      <Dialog open={leaveDialogOpen} onOpenChange={setLeaveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>申请请假</DialogTitle>
            <DialogDescription>填写请假信息，1天以内自动审批</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>请假类型</Label>
              <Select
                value={leaveForm.leave_type}
                onValueChange={(v) => setLeaveForm({ ...leaveForm, leave_type: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="annual">年假</SelectItem>
                  <SelectItem value="sick">病假</SelectItem>
                  <SelectItem value="personal">事假</SelectItem>
                  <SelectItem value="marriage">婚假</SelectItem>
                  <SelectItem value="maternity">产假</SelectItem>
                  <SelectItem value="bereavement">丧假</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>开始日期</Label>
                <Input
                  type="date"
                  value={leaveForm.start_date}
                  onChange={(e) => setLeaveForm({ ...leaveForm, start_date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>结束日期</Label>
                <Input
                  type="date"
                  value={leaveForm.end_date}
                  onChange={(e) => setLeaveForm({ ...leaveForm, end_date: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>请假事由</Label>
              <Textarea
                placeholder="请描述请假原因..."
                value={leaveForm.reason}
                onChange={(e) => setLeaveForm({ ...leaveForm, reason: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLeaveDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleSubmitLeave} disabled={leaveSubmitting}>
              {leaveSubmitting && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              提交申请
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 会议 Dialog */}
      <Dialog open={meetingDialogOpen} onOpenChange={setMeetingDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>预约会议</DialogTitle>
            <DialogDescription>填写会议信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>会议主题</Label>
              <Input
                placeholder="请输入会议主题"
                value={meetingForm.title}
                onChange={(e) => setMeetingForm({ ...meetingForm, title: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>开始时间</Label>
                <Input
                  type="datetime-local"
                  value={meetingForm.start_time}
                  onChange={(e) => setMeetingForm({ ...meetingForm, start_time: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>结束时间</Label>
                <Input
                  type="datetime-local"
                  value={meetingForm.end_time}
                  onChange={(e) => setMeetingForm({ ...meetingForm, end_time: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMeetingDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleSubmitMeeting} disabled={meetingSubmitting}>
              {meetingSubmitting && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              预约
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 任务 Dialog */}
      <Dialog open={taskDialogOpen} onOpenChange={setTaskDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建任务</DialogTitle>
            <DialogDescription>创建新任务并分配</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>任务标题</Label>
              <Input
                placeholder="请输入任务标题"
                value={taskForm.title}
                onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>任务描述</Label>
              <Textarea
                placeholder="请描述任务内容..."
                value={taskForm.description}
                onChange={(e) => setTaskForm({ ...taskForm, description: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>优先级</Label>
                <Select
                  value={taskForm.priority}
                  onValueChange={(v) => setTaskForm({ ...taskForm, priority: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">低</SelectItem>
                    <SelectItem value="medium">中</SelectItem>
                    <SelectItem value="high">高</SelectItem>
                    <SelectItem value="urgent">紧急</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>截止日期</Label>
                <Input
                  type="date"
                  value={taskForm.due_date}
                  onChange={(e) => setTaskForm({ ...taskForm, due_date: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTaskDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleSubmitTask} disabled={taskSubmitting}>
              {taskSubmitting && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              创建任务
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default OACenter;

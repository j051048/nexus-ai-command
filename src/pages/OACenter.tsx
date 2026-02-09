/**
 * OA 办公中心
 * 整合请假、会议、任务等办公功能
 */

import React, { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { format } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { cn } from '@/lib/utils';
import {
  Calendar as CalendarIcon,
  Clock,
  Users,
  FileText,
  CheckCircle2,
  XCircle,
  Clock3,
  Plus,
  Send,
  MessageSquare,
  Briefcase,
} from 'lucide-react';
import { useUser } from '@/contexts/UserContext';
import { toast } from 'sonner';

// 请假类型配置
const leaveTypes = [
  { value: 'annual', label: '年假', icon: '🏖️' },
  { value: 'sick', label: '病假', icon: '🏥' },
  { value: 'personal', label: '事假', icon: '📋' },
  { value: 'compensatory', label: '调休', icon: '🔄' },
];

// 模拟请假记录
const mockLeaveRecords = [
  { id: '1', type: 'annual', startDate: '2024-12-20', endDate: '2024-12-22', days: 3, status: 'approved', reason: '回老家' },
  { id: '2', type: 'sick', startDate: '2024-12-10', endDate: '2024-12-10', days: 1, status: 'approved', reason: '感冒' },
  { id: '3', type: 'personal', startDate: '2024-12-25', endDate: '2024-12-26', days: 2, status: 'pending', reason: '家中有事' },
];

// 模拟会议记录
const mockMeetings = [
  { id: '1', title: '周例会', room: '会议室301', time: '2024-12-20 10:00', attendees: 8, status: 'upcoming' },
  { id: '2', title: '项目评审', room: '会议室302', time: '2024-12-21 14:00', attendees: 5, status: 'upcoming' },
  { id: '3', title: '客户拜访总结', room: '洽谈室A', time: '2024-12-19 15:00', attendees: 3, status: 'completed' },
];

// 模拟任务记录
const mockTasks = [
  { id: '1', title: '完成华为项目方案', assignee: '我', dueDate: '2024-12-22', priority: 'high', status: 'in_progress' },
  { id: '2', title: '整理客户资料', assignee: '我', dueDate: '2024-12-23', priority: 'medium', status: 'todo' },
  { id: '3', title: '提交周报', assignee: '我', dueDate: '2024-12-20', priority: 'low', status: 'done' },
];

export function OACenter() {
  const { user } = useUser();
  const [activeTab, setActiveTab] = useState('leave');
  const [leaveDate, setLeaveDate] = useState<Date | undefined>(new Date());
  const [leaveEndDate, setLeaveEndDate] = useState<Date | undefined>(new Date());

  const handleQuickLeave = () => {
    toast.success('已跳转到AI助手，请用自然语言描述您的请假需求');
    // TODO: 打开AI对话并预填请假意图
  };

  const statusConfig = {
    pending: { label: '审批中', icon: <Clock3 className="w-4 h-4" />, color: 'text-yellow-500 bg-yellow-500/10' },
    approved: { label: '已通过', icon: <CheckCircle2 className="w-4 h-4" />, color: 'text-green-500 bg-green-500/10' },
    rejected: { label: '已拒绝', icon: <XCircle className="w-4 h-4" />, color: 'text-red-500 bg-red-500/10' },
  };

  const priorityConfig = {
    high: { label: '紧急', color: 'bg-red-500' },
    medium: { label: '普通', color: 'bg-yellow-500' },
    low: { label: '较低', color: 'bg-green-500' },
  };

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">OA 办公中心</h1>
          <p className="text-muted-foreground">管理您的请假、会议和任务</p>
        </div>
        <Button onClick={handleQuickLeave} className="gap-2">
          <MessageSquare className="w-4 h-4" />
          用AI助手办理
        </Button>
      </div>

      {/* 快捷统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">年假余额</p>
                <p className="text-2xl font-bold">7 天</p>
              </div>
              <div className="p-3 rounded-full bg-blue-500/10">
                <CalendarIcon className="w-6 h-6 text-blue-500" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">待审批</p>
                <p className="text-2xl font-bold">1 条</p>
              </div>
              <div className="p-3 rounded-full bg-yellow-500/10">
                <Clock3 className="w-6 h-6 text-yellow-500" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">今日会议</p>
                <p className="text-2xl font-bold">2 场</p>
              </div>
              <div className="p-3 rounded-full bg-purple-500/10">
                <Users className="w-6 h-6 text-purple-500" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">待办任务</p>
                <p className="text-2xl font-bold">3 项</p>
              </div>
              <div className="p-3 rounded-full bg-green-500/10">
                <Briefcase className="w-6 h-6 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 主内容区 */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="leave" className="gap-2">
            <CalendarIcon className="w-4 h-4" />
            请假管理
          </TabsTrigger>
          <TabsTrigger value="meeting" className="gap-2">
            <Users className="w-4 h-4" />
            会议管理
          </TabsTrigger>
          <TabsTrigger value="task" className="gap-2">
            <FileText className="w-4 h-4" />
            任务管理
          </TabsTrigger>
        </TabsList>

        {/* 请假管理 */}
        <TabsContent value="leave" className="space-y-4">
          <div className="grid md:grid-cols-2 gap-6">
            {/* 请假申请表单 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">发起请假</CardTitle>
                <CardDescription>填写请假信息或使用AI助手快速申请</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>请假类型</Label>
                  <Select defaultValue="annual">
                    <SelectTrigger>
                      <SelectValue placeholder="选择请假类型" />
                    </SelectTrigger>
                    <SelectContent>
                      {leaveTypes.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.icon} {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>开始日期</Label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button variant="outline" className="w-full justify-start text-left font-normal">
                          <CalendarIcon className="mr-2 h-4 w-4" />
                          {leaveDate ? format(leaveDate, 'yyyy-MM-dd') : '选择日期'}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0">
                        <Calendar
                          mode="single"
                          selected={leaveDate}
                          onSelect={setLeaveDate}
                          locale={zhCN}
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                  <div className="space-y-2">
                    <Label>结束日期</Label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button variant="outline" className="w-full justify-start text-left font-normal">
                          <CalendarIcon className="mr-2 h-4 w-4" />
                          {leaveEndDate ? format(leaveEndDate, 'yyyy-MM-dd') : '选择日期'}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0">
                        <Calendar
                          mode="single"
                          selected={leaveEndDate}
                          onSelect={setLeaveEndDate}
                          locale={zhCN}
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>请假原因</Label>
                  <Textarea placeholder="请输入请假原因..." />
                </div>

                <div className="flex gap-2">
                  <Button className="flex-1 gap-2">
                    <Send className="w-4 h-4" />
                    提交申请
                  </Button>
                  <Button variant="outline" onClick={handleQuickLeave} className="gap-2">
                    <MessageSquare className="w-4 h-4" />
                    AI助手
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* 请假记录 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">请假记录</CardTitle>
                <CardDescription>最近的请假申请</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {mockLeaveRecords.map((record) => {
                    const status = statusConfig[record.status as keyof typeof statusConfig];
                    const leaveType = leaveTypes.find(t => t.value === record.type);
                    return (
                      <div key={record.id} className="flex items-center justify-between p-3 rounded-lg border">
                        <div className="flex items-center gap-3">
                          <span className="text-2xl">{leaveType?.icon}</span>
                          <div>
                            <p className="font-medium">{leaveType?.label} {record.days}天</p>
                            <p className="text-sm text-muted-foreground">
                              {record.startDate} ~ {record.endDate}
                            </p>
                          </div>
                        </div>
                        <Badge className={cn('gap-1', status.color)}>
                          {status.icon}
                          {status.label}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* 会议管理 */}
        <TabsContent value="meeting" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">我的会议</h3>
            <Button className="gap-2">
              <Plus className="w-4 h-4" />
              预约会议
            </Button>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {mockMeetings.map((meeting) => (
              <Card key={meeting.id}>
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    <div className="flex items-start justify-between">
                      <h4 className="font-medium">{meeting.title}</h4>
                      <Badge variant={meeting.status === 'upcoming' ? 'default' : 'secondary'}>
                        {meeting.status === 'upcoming' ? '即将开始' : '已结束'}
                      </Badge>
                    </div>
                    <div className="space-y-1 text-sm text-muted-foreground">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4" />
                        {meeting.time}
                      </div>
                      <div className="flex items-center gap-2">
                        <Briefcase className="w-4 h-4" />
                        {meeting.room}
                      </div>
                      <div className="flex items-center gap-2">
                        <Users className="w-4 h-4" />
                        {meeting.attendees} 人参会
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* 任务管理 */}
        <TabsContent value="task" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">我的任务</h3>
            <Button className="gap-2">
              <Plus className="w-4 h-4" />
              新建任务
            </Button>
          </div>
          <div className="space-y-3">
            {mockTasks.map((task) => {
              const priority = priorityConfig[task.priority as keyof typeof priorityConfig];
              return (
                <Card key={task.id}>
                  <CardContent className="py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={cn('w-2 h-2 rounded-full', priority.color)} />
                        <div>
                          <p className="font-medium">{task.title}</p>
                          <p className="text-sm text-muted-foreground">截止: {task.dueDate}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{priority.label}</Badge>
                        <Badge variant={
                          task.status === 'done' ? 'default' :
                          task.status === 'in_progress' ? 'secondary' : 'outline'
                        }>
                          {task.status === 'done' ? '已完成' :
                           task.status === 'in_progress' ? '进行中' : '待开始'}
                        </Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default OACenter;
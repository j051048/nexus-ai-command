/**
 * HR 人事中心
 * 整合考勤、薪资、绩效等人事功能
 */

import React, { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import {
  Clock,
  Calendar,
  DollarSign,
  TrendingUp,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Users,
  Award,
  BarChart3,
  MessageSquare,
} from 'lucide-react';
import { useUser } from '@/contexts/UserContext';
import { toast } from 'sonner';

// 模拟考勤数据
const mockAttendance = {
  month: '2024年12月',
  workDays: 22,
  actualDays: 20,
  lateTimes: 2,
  earlyLeaveTimes: 0,
  overtimeHours: 15.5,
  records: [
    { date: '2024-12-20', checkIn: '09:05', checkOut: '18:30', status: 'late', note: '迟到5分钟' },
    { date: '2024-12-19', checkIn: '08:55', checkOut: '19:00', status: 'normal', note: '加班1小时' },
    { date: '2024-12-18', checkIn: '08:50', checkOut: '18:00', status: 'normal', note: '' },
    { date: '2024-12-17', checkIn: '09:10', checkOut: '18:30', status: 'late', note: '迟到10分钟' },
    { date: '2024-12-16', checkIn: '08:45', checkOut: '18:00', status: 'normal', note: '' },
  ],
};

// 模拟薪资数据
const mockSalary = {
  period: '2024年12月',
  baseSalary: 15000,
  performanceBonus: 3200,
  attendanceBonus: 500,
  mealAllowance: 500,
  grossSalary: 19200,
  socialInsurance: 1890,
  housingFund: 2400,
  tax: 892,
  otherDeductions: 200,
  netSalary: 13818,
  paymentDate: '2024-12-10',
  status: 'paid',
};

// 模拟绩效数据
const mockPerformance = {
  currentScore: 87,
  rank: 5,
  totalEmployees: 45,
  trend: '+5',
  metrics: [
    { name: '销售业绩', score: 92, weight: 40 },
    { name: '客户满意度', score: 88, weight: 20 },
    { name: '团队协作', score: 85, weight: 15 },
    { name: '任务完成率', score: 80, weight: 15 },
    { name: '学习成长', score: 82, weight: 10 },
  ],
  badges: [
    { name: '销售新星', icon: '⭐', date: '2024-12-15' },
    { name: '全勤标兵', icon: '🏆', date: '2024-11-30' },
    { name: '客户之友', icon: '🤝', date: '2024-10-20' },
  ],
};

export function HRCenter() {
  const { user } = useUser();
  const [activeTab, setActiveTab] = useState('attendance');

  const handleAIQuery = (query: string) => {
    toast.success(`已跳转到AI助手: ${query}`);
  };

  const statusConfig = {
    normal: { label: '正常', color: 'text-green-500 bg-green-500/10' },
    late: { label: '迟到', color: 'text-yellow-500 bg-yellow-500/10' },
    early_leave: { label: '早退', color: 'text-orange-500 bg-orange-500/10' },
    absent: { label: '缺勤', color: 'text-red-500 bg-red-500/10' },
    leave: { label: '请假', color: 'text-blue-500 bg-blue-500/10' },
  };

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">HR 人事中心</h1>
          <p className="text-muted-foreground">查看考勤、薪资和绩效信息</p>
        </div>
        <Button onClick={() => handleAIQuery('查询我的人事信息')} className="gap-2">
          <MessageSquare className="w-4 h-4" />
          用AI助手查询
        </Button>
      </div>

      {/* 主内容区 */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="attendance" className="gap-2">
            <Clock className="w-4 h-4" />
            考勤记录
          </TabsTrigger>
          <TabsTrigger value="salary" className="gap-2">
            <DollarSign className="w-4 h-4" />
            薪资明细
          </TabsTrigger>
          <TabsTrigger value="performance" className="gap-2">
            <TrendingUp className="w-4 h-4" />
            绩效评估
          </TabsTrigger>
        </TabsList>

        {/* 考勤记录 */}
        <TabsContent value="attendance" className="space-y-4">
          {/* 考勤统计卡片 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">出勤天数</p>
                    <p className="text-2xl font-bold">{mockAttendance.actualDays}/{mockAttendance.workDays}</p>
                  </div>
                  <div className="p-3 rounded-full bg-green-500/10">
                    <CheckCircle2 className="w-6 h-6 text-green-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">迟到次数</p>
                    <p className="text-2xl font-bold text-yellow-500">{mockAttendance.lateTimes}</p>
                  </div>
                  <div className="p-3 rounded-full bg-yellow-500/10">
                    <AlertCircle className="w-6 h-6 text-yellow-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">加班时长</p>
                    <p className="text-2xl font-bold">{mockAttendance.overtimeHours}h</p>
                  </div>
                  <div className="p-3 rounded-full bg-blue-500/10">
                    <Clock className="w-6 h-6 text-blue-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">出勤率</p>
                    <p className="text-2xl font-bold">
                      {((mockAttendance.actualDays / mockAttendance.workDays) * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="p-3 rounded-full bg-purple-500/10">
                    <BarChart3 className="w-6 h-6 text-purple-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 考勤明细 */}
          <Card>
            <CardHeader>
              <CardTitle>考勤明细 - {mockAttendance.month}</CardTitle>
              <CardDescription>最近的打卡记录</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {mockAttendance.records.map((record, index) => {
                  const status = statusConfig[record.status as keyof typeof statusConfig];
                  return (
                    <div key={index} className="flex items-center justify-between p-3 rounded-lg border">
                      <div className="flex items-center gap-4">
                        <div className="text-center">
                          <p className="font-medium">{record.date}</p>
                        </div>
                        <div className="flex items-center gap-6 text-sm">
                          <div>
                            <span className="text-muted-foreground">上班: </span>
                            <span className="font-medium">{record.checkIn}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">下班: </span>
                            <span className="font-medium">{record.checkOut}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {record.note && (
                          <span className="text-sm text-muted-foreground">{record.note}</span>
                        )}
                        <Badge className={status.color}>{status.label}</Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 薪资明细 */}
        <TabsContent value="salary" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>薪资明细 - {mockSalary.period}</CardTitle>
                  <CardDescription>
                    发放日期: {mockSalary.paymentDate} 
                    <Badge className="ml-2" variant="outline">
                      {mockSalary.status === 'paid' ? '✅ 已发放' : '⏳ 待发放'}
                    </Badge>
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-6">
                {/* 收入项 */}
                <div className="space-y-4">
                  <h4 className="font-medium text-green-600 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />
                    收入项
                  </h4>
                  <div className="space-y-2 p-4 rounded-lg bg-green-50 dark:bg-green-950/20">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">基本工资</span>
                      <span className="font-medium">¥{mockSalary.baseSalary.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">绩效奖金</span>
                      <span className="font-medium">¥{mockSalary.performanceBonus.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">全勤奖</span>
                      <span className="font-medium">¥{mockSalary.attendanceBonus.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">餐补</span>
                      <span className="font-medium">¥{mockSalary.mealAllowance.toLocaleString()}</span>
                    </div>
                    <div className="border-t pt-2 flex justify-between font-medium">
                      <span>应发合计</span>
                      <span className="text-green-600">¥{mockSalary.grossSalary.toLocaleString()}</span>
                    </div>
                  </div>
                </div>

                {/* 扣除项 */}
                <div className="space-y-4">
                  <h4 className="font-medium text-red-600 flex items-center gap-2">
                    <XCircle className="w-4 h-4" />
                    扣除项
                  </h4>
                  <div className="space-y-2 p-4 rounded-lg bg-red-50 dark:bg-red-950/20">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">社保</span>
                      <span className="font-medium">-¥{mockSalary.socialInsurance.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">公积金</span>
                      <span className="font-medium">-¥{mockSalary.housingFund.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">个税</span>
                      <span className="font-medium">-¥{mockSalary.tax.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">其他扣款</span>
                      <span className="font-medium">-¥{mockSalary.otherDeductions.toLocaleString()}</span>
                    </div>
                    <div className="border-t pt-2 flex justify-between font-medium">
                      <span>扣除合计</span>
                      <span className="text-red-600">
                        -¥{(mockSalary.socialInsurance + mockSalary.housingFund + mockSalary.tax + mockSalary.otherDeductions).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 实发工资 */}
              <div className="mt-6 p-6 rounded-xl bg-gradient-to-r from-primary/10 to-primary/5 border">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">实发工资</p>
                    <p className="text-3xl font-bold">¥{mockSalary.netSalary.toLocaleString()}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">到账银行</p>
                    <p className="font-medium">工商银行 (尾号6688)</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 绩效评估 */}
        <TabsContent value="performance" className="space-y-4">
          <div className="grid md:grid-cols-3 gap-4">
            {/* 绩效得分卡片 */}
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>绩效得分</CardTitle>
                <CardDescription>当前考核周期: 2024年Q4</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-8 mb-6">
                  <div className="text-center">
                    <div className="text-5xl font-bold text-primary">{mockPerformance.currentScore}</div>
                    <p className="text-sm text-muted-foreground mt-1">综合得分</p>
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span>团队排名</span>
                      <span className="font-medium">第 {mockPerformance.rank} 名 / {mockPerformance.totalEmployees} 人</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span>环比变化</span>
                      <span className="font-medium text-green-500">{mockPerformance.trend} 分</span>
                    </div>
                  </div>
                </div>

                {/* 各维度得分 */}
                <div className="space-y-4">
                  {mockPerformance.metrics.map((metric) => (
                    <div key={metric.name} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span>{metric.name}</span>
                        <span className="font-medium">{metric.score}分 (权重{metric.weight}%)</span>
                      </div>
                      <Progress value={metric.score} className="h-2" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* 荣誉徽章 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Award className="w-5 h-5 text-yellow-500" />
                  荣誉徽章
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {mockPerformance.badges.map((badge, index) => (
                    <div key={index} className="flex items-center gap-3 p-3 rounded-lg border">
                      <span className="text-2xl">{badge.icon}</span>
                      <div>
                        <p className="font-medium">{badge.name}</p>
                        <p className="text-xs text-muted-foreground">{badge.date}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default HRCenter;
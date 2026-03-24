/**
 * HR 人事中心
 * 整合考勤、薪资、绩效、招聘等人事功能
 */

import React, { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  Clock,
  DollarSign,
  TrendingUp,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Award,
  BarChart3,
  MessageSquare,
  Briefcase,
  Users,
  Loader2,
} from 'lucide-react';
import { useUser } from '@/contexts/UserContext';
import { toast } from 'sonner';
import {
  useAttendanceStats,
  useSalaryRecords,
  usePerformanceData,
  useRecruitmentList,
  useCandidates,
  type AttendanceRecord,
  type SalaryRecord,
  type PerformanceReview,
  type JobPosition,
} from '@/hooks/useHRData';

const statusConfig: Record<string, { label: string; color: string }> = {
  normal: { label: '正常', color: 'text-green-500 bg-green-500/10' },
  late: { label: '迟到', color: 'text-yellow-500 bg-yellow-500/10' },
  early_leave: { label: '早退', color: 'text-orange-500 bg-orange-500/10' },
  absent: { label: '缺勤', color: 'text-red-500 bg-red-500/10' },
  leave: { label: '请假', color: 'text-blue-500 bg-blue-500/10' },
};

const positionStatusConfig: Record<string, { label: string; color: string }> = {
  open: { label: '招聘中', color: 'text-green-500 bg-green-500/10' },
  paused: { label: '暂停', color: 'text-yellow-500 bg-yellow-500/10' },
  closed: { label: '已关闭', color: 'text-gray-500 bg-gray-500/10' },
};

export function HRCenter() {
  const { user } = useUser();
  const [activeTab, setActiveTab] = useState('attendance');
  const [selectedMonth] = useState(() => new Date().toISOString().slice(0, 7));

  const handleAIQuery = (query: string) => {
    toast.success(`已跳转到AI助手: ${query}`);
  };

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold">HR 人事中心</h1>
          <p className="text-muted-foreground">查看考勤、薪资、绩效和招聘信息</p>
        </div>
        <Button onClick={() => handleAIQuery('查询我的人事信息')} className="gap-2">
          <MessageSquare className="w-4 h-4" />
          用AI助手查询
        </Button>
      </div>

      {/* 主内容区 */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
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
          <TabsTrigger value="recruitment" className="gap-2">
            <Briefcase className="w-4 h-4" />
            招聘管理
          </TabsTrigger>
        </TabsList>

        <TabsContent value="attendance">
          <AttendanceTab month={selectedMonth} />
        </TabsContent>
        <TabsContent value="salary">
          <SalaryTab period={selectedMonth} />
        </TabsContent>
        <TabsContent value="performance">
          <PerformanceTab />
        </TabsContent>
        <TabsContent value="recruitment">
          <RecruitmentTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ────────────────── Attendance Tab ────────────────── */
function AttendanceTab({ month }: { month: string }) {
  const { stats, records, isLoading } = useAttendanceStats(month);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-24 rounded-lg" />)}
        </div>
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="text-center py-16 bg-muted/10 rounded-xl border border-dashed">
        <Clock className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium">暂无考勤数据</h3>
        <p className="text-muted-foreground mt-1">当月考勤记录将在打卡后显示</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 考勤统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">出勤天数</p>
                <p className="text-2xl font-bold">{stats.actualDays}/{stats.workDays}</p>
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
                <p className="text-2xl font-bold text-yellow-500">{stats.lateTimes}</p>
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
                <p className="text-2xl font-bold">{stats.overtimeHours.toFixed(1)}h</p>
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
                <p className="text-2xl font-bold">{stats.attendanceRate.toFixed(1)}%</p>
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
          <CardTitle>考勤明细 - {month}</CardTitle>
          <CardDescription>最近的打卡记录</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {records.map((record) => {
              const status = statusConfig[record.status] || statusConfig.normal;
              const checkInTime = record.check_in ? new Date(record.check_in).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '--:--';
              const checkOutTime = record.check_out ? new Date(record.check_out).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '--:--';
              return (
                <div key={record.id} className="flex items-center justify-between p-3 rounded-lg border">
                  <div className="flex items-center gap-4">
                    <div className="text-center">
                      <p className="font-medium">{record.date}</p>
                    </div>
                    <div className="flex items-center gap-6 text-sm">
                      <div>
                        <span className="text-muted-foreground">上班: </span>
                        <span className="font-medium">{checkInTime}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">下班: </span>
                        <span className="font-medium">{checkOutTime}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {record.late_minutes > 0 && (
                      <span className="text-sm text-muted-foreground">迟到{record.late_minutes}分钟</span>
                    )}
                    {record.overtime_hours > 0 && (
                      <span className="text-sm text-muted-foreground">加班{record.overtime_hours}h</span>
                    )}
                    <Badge className={status.color}>{status.label}</Badge>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/* ────────────────── Salary Tab ────────────────── */
function SalaryTab({ period }: { period: string }) {
  const { data: salary, isLoading } = useSalaryRecords(period);

  if (isLoading) {
    return <Skeleton className="h-96 rounded-lg" />;
  }

  if (!salary) {
    return (
      <div className="text-center py-16 bg-muted/10 rounded-xl border border-dashed">
        <DollarSign className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium">暂无薪资数据</h3>
        <p className="text-muted-foreground mt-1">{period} 的薪资明细尚未生成，请联系人事部门</p>
      </div>
    );
  }

  const grossSalary = Number(salary.gross_salary || 0);
  const totalDeductions = Number(salary.social_insurance || 0) + Number(salary.housing_fund || 0) + Number(salary.tax || 0) + Number(salary.other_deductions || 0);
  const netSalary = Number(salary.net_salary || 0);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>薪资明细 - {salary.period}</CardTitle>
              <CardDescription>
                {salary.payment_date && `发放日期: ${salary.payment_date}`}
                <Badge className="ml-2" variant="outline">
                  {salary.payment_status === 'paid' ? '已发放' : '待发放'}
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
                  <span className="font-medium">{'\u00A5'}{Number(salary.base_salary || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">绩效奖金</span>
                  <span className="font-medium">{'\u00A5'}{Number(salary.performance_bonus || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">全勤奖</span>
                  <span className="font-medium">{'\u00A5'}{Number(salary.attendance_bonus || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">其他津贴</span>
                  <span className="font-medium">{'\u00A5'}{Number(salary.other_allowances || 0).toLocaleString()}</span>
                </div>
                <div className="border-t pt-2 flex justify-between font-medium">
                  <span>应发合计</span>
                  <span className="text-green-600">{'\u00A5'}{grossSalary.toLocaleString()}</span>
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
                  <span className="font-medium">-{'\u00A5'}{Number(salary.social_insurance || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">公积金</span>
                  <span className="font-medium">-{'\u00A5'}{Number(salary.housing_fund || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">个税</span>
                  <span className="font-medium">-{'\u00A5'}{Number(salary.tax || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">其他扣款</span>
                  <span className="font-medium">-{'\u00A5'}{Number(salary.other_deductions || 0).toLocaleString()}</span>
                </div>
                <div className="border-t pt-2 flex justify-between font-medium">
                  <span>扣除合计</span>
                  <span className="text-red-600">-{'\u00A5'}{totalDeductions.toLocaleString()}</span>
                </div>
              </div>
            </div>
          </div>

          {/* 实发工资 */}
          <div className="mt-6 p-6 rounded-xl bg-gradient-to-r from-primary/10 to-primary/5 border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">实发工资</p>
                <p className="text-3xl font-bold">{'\u00A5'}{netSalary.toLocaleString()}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/* ────────────────── Performance Tab ────────────────── */
function PerformanceTab() {
  const { data: review, isLoading } = usePerformanceData();

  if (isLoading) {
    return <Skeleton className="h-64 rounded-lg" />;
  }

  if (!review) {
    return (
      <div className="text-center py-16 bg-muted/10 rounded-xl border border-dashed">
        <TrendingUp className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium">暂无绩效数据</h3>
        <p className="text-muted-foreground mt-1">当前考核周期的绩效评估尚未开始</p>
      </div>
    );
  }

  const finalScore = Number(review.final_rating || review.manager_rating || review.self_rating || 0);
  const goals = Array.isArray(review.goals) ? review.goals : [];

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-3 gap-4">
        {/* 绩效得分卡片 */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>绩效得分</CardTitle>
            <CardDescription>考核周期: {review.period}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-8 mb-6">
              <div className="text-center">
                <div className="text-5xl font-bold text-primary">{(finalScore * 20).toFixed(0)}</div>
                <p className="text-sm text-muted-foreground mt-1">综合得分</p>
              </div>
              <div className="flex-1 space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span>自评分</span>
                  <span className="font-medium">{review.self_rating ? (Number(review.self_rating) * 20).toFixed(0) : '-'}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span>主管评分</span>
                  <span className="font-medium">{review.manager_rating ? (Number(review.manager_rating) * 20).toFixed(0) : '-'}</span>
                </div>
                {review.ai_rating && (
                  <div className="flex items-center justify-between text-sm">
                    <span>AI 评估</span>
                    <span className="font-medium">{(Number(review.ai_rating) * 20).toFixed(0)}</span>
                  </div>
                )}
                <div className="flex items-center justify-between text-sm">
                  <span>状态</span>
                  <Badge variant="outline">{review.status}</Badge>
                </div>
              </div>
            </div>

            {/* 目标完成情况 */}
            {goals.length > 0 && (
              <div className="space-y-4">
                <h4 className="font-medium">目标完成情况</h4>
                {goals.map((goal, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span>{goal.title}</span>
                      <span className="font-medium">{(goal.completion_rate * 100).toFixed(0)}%</span>
                    </div>
                    <Progress value={goal.completion_rate * 100} className="h-2" />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 评语 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Award className="w-5 h-5 text-yellow-500" />
              评价与建议
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {review.strengths && (
                <div>
                  <p className="text-sm font-medium text-green-600 mb-1">优势</p>
                  <p className="text-sm text-muted-foreground">{review.strengths}</p>
                </div>
              )}
              {review.improvements && (
                <div>
                  <p className="text-sm font-medium text-orange-600 mb-1">待改进</p>
                  <p className="text-sm text-muted-foreground">{review.improvements}</p>
                </div>
              )}
              {review.ai_analysis && (
                <div>
                  <p className="text-sm font-medium text-blue-600 mb-1">AI 分析</p>
                  <p className="text-sm text-muted-foreground">{review.ai_analysis}</p>
                </div>
              )}
              {!review.strengths && !review.improvements && !review.ai_analysis && (
                <p className="text-sm text-muted-foreground">暂无评价内容</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/* ────────────────── Recruitment Tab ────────────────── */
function RecruitmentTab() {
  const { data: positions = [], isLoading } = useRecruitmentList();
  const [selectedPositionId, setSelectedPositionId] = useState<string | null>(null);
  const { data: candidates = [], isLoading: candidatesLoading } = useCandidates(selectedPositionId);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 rounded-lg" />)}
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="text-center py-16 bg-muted/10 rounded-xl border border-dashed">
        <Briefcase className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium">暂无招聘岗位</h3>
        <p className="text-muted-foreground mt-1">招聘信息将由 HR 管理员创建后显示</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 岗位统计 */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">招聘中</p>
                <p className="text-2xl font-bold">{positions.filter(p => p.status === 'open').length}</p>
              </div>
              <div className="p-3 rounded-full bg-green-500/10">
                <Briefcase className="w-6 h-6 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">待招人数</p>
                <p className="text-2xl font-bold">
                  {positions.reduce((sum, p) => sum + (p.headcount - p.hired_count), 0)}
                </p>
              </div>
              <div className="p-3 rounded-full bg-blue-500/10">
                <Users className="w-6 h-6 text-blue-500" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">已入职</p>
                <p className="text-2xl font-bold text-green-500">
                  {positions.reduce((sum, p) => sum + p.hired_count, 0)}
                </p>
              </div>
              <div className="p-3 rounded-full bg-green-500/10">
                <CheckCircle2 className="w-6 h-6 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 岗位列表 */}
      <Card>
        <CardHeader>
          <CardTitle>招聘岗位列表</CardTitle>
          <CardDescription>点击岗位查看候选人</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {positions.map(position => {
              const statusCfg = positionStatusConfig[position.status] || positionStatusConfig.open;
              const isSelected = selectedPositionId === position.id;
              return (
                <div key={position.id}>
                  <div
                    className={cn(
                      'flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors',
                      isSelected ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                    )}
                    onClick={() => setSelectedPositionId(isSelected ? null : position.id)}
                  >
                    <div>
                      <p className="font-medium">{position.title}</p>
                      <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
                        {position.department && <span>{position.department}</span>}
                        <span>招 {position.headcount} 人 / 已入 {position.hired_count} 人</span>
                        {position.salary_range_min && position.salary_range_max && (
                          <span>{'\u00A5'}{Number(position.salary_range_min).toLocaleString()}-{Number(position.salary_range_max).toLocaleString()}</span>
                        )}
                      </div>
                    </div>
                    <Badge className={statusCfg.color}>{statusCfg.label}</Badge>
                  </div>

                  {/* 候选人展开区 */}
                  {isSelected && (
                    <div className="ml-4 mt-2 mb-3 p-3 rounded-lg bg-muted/30 border-l-2 border-primary">
                      {candidatesLoading ? (
                        <div className="flex items-center gap-2 py-2">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span className="text-sm text-muted-foreground">加载候选人...</span>
                        </div>
                      ) : candidates.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-2">暂无候选人</p>
                      ) : (
                        <div className="space-y-2">
                          {candidates.map(c => (
                            <div key={c.id} className="flex items-center justify-between p-2 rounded border bg-background">
                              <div>
                                <p className="text-sm font-medium">{c.name}</p>
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                  {c.email && <span>{c.email}</span>}
                                  {c.phone && <span>{c.phone}</span>}
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                {c.ai_score != null && (
                                  <Badge variant="outline" className="text-xs">AI: {c.ai_score}分</Badge>
                                )}
                                <Badge variant="secondary" className="text-xs">{c.status}</Badge>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default HRCenter;

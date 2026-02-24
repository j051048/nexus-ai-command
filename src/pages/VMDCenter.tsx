/**
 * 虚拟市场部 - 工作台主页
 * Hero + 快捷场景卡片 + 统计概览 + 最近任务
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Rocket,
  ClipboardList,
  Tent,
  PenTool,
  FlaskConical,
  Handshake,
  ListTodo,
  Bot,
  Target,
  ShieldCheck,
  BarChart3,
  Cpu,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { useVMDStats, useVMDTasks } from '@/hooks/useVMD';
import { cn } from '@/lib/utils';

// 场景卡片配置
const SCENE_CARDS = [
  { code: 'new_product_launch', name: '新品上市策划', description: '全案策划与执行', icon: Rocket, color: 'text-blue-500', bg: 'bg-blue-500/10' },
  { code: 'bid_support', name: '招投标支持', description: '标书生成与合规校验', icon: ClipboardList, color: 'text-amber-500', bg: 'bg-amber-500/10' },
  { code: 'exhibition', name: '展会运营', description: '展会全流程管理', icon: Tent, color: 'text-purple-500', bg: 'bg-purple-500/10' },
  { code: 'content_marketing', name: '日常内容营销', description: '内容生成与投放', icon: PenTool, color: 'text-green-500', bg: 'bg-green-500/10' },
  { code: 'rnd_synergy', name: '研产销协同', description: '市场洞察与需求协同', icon: FlaskConical, color: 'text-cyan-500', bg: 'bg-cyan-500/10' },
  { code: 'after_sales', name: '售后运营', description: '客户生命周期管理', icon: Handshake, color: 'text-rose-500', bg: 'bg-rose-500/10' },
];

// 快捷导航
const QUICK_NAV = [
  { label: '任务中心', path: '/vmd/tasks', icon: ListTodo },
  { label: 'Agent配置', path: '/vmd/agents', icon: Bot },
  { label: '线索管理', path: '/vmd/clues', icon: Target },
  { label: '合规校验', path: '/vmd/compliance', icon: ShieldCheck },
  { label: '数据看板', path: '/vmd/dashboard', icon: BarChart3 },
  { label: '模型管理', path: '/llm/models', icon: Cpu },
];

// 状态配色
const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300' },
  planning: { label: '规划中', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' },
  executing: { label: '执行中', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300' },
  reviewing: { label: '审核中', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300' },
  done: { label: '已完成', color: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' },
  failed: { label: '失败', color: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' },
};

const SCENE_NAMES: Record<string, string> = {
  new_product_launch: '新品上市',
  bid_support: '招投标',
  exhibition: '展会运营',
  content_marketing: '内容营销',
  rnd_synergy: '研产销协同',
  after_sales: '售后运营',
};

export default function VMDCenter() {
  const navigate = useNavigate();
  const { data: stats, isLoading: statsLoading } = useVMDStats();
  const { data: tasks, isLoading: tasksLoading } = useVMDTasks({});

  const recentTasks = (tasks || []).slice(0, 5);

  const handleSceneStart = (sceneCode: string) => {
    navigate(`/vmd/tasks?scene=${sceneCode}&new=1`);
  };

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* Hero 区域 */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-primary/10 via-primary/5 to-transparent border border-primary/20 p-6 md:p-8">
        <div className="relative z-10">
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight mb-2">
            虚拟市场部
          </h1>
          <p className="text-muted-foreground max-w-xl">
            AI Agent 驱动的智能市场营销协作平台。覆盖新品上市、招投标、展会运营、内容营销等六大核心场景，
            10个专业 Agent 协同工作，实现从策划到执行的全流程自动化。
          </p>
        </div>
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full -translate-y-1/2 translate-x-1/2" />
      </div>

      {/* 统计概览 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statsLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}><CardContent className="pt-6"><Skeleton className="h-16 w-full" /></CardContent></Card>
          ))
        ) : (
          <>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                    <ListTodo className="w-5 h-5 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">今日任务数</p>
                    <p className="text-2xl font-bold">{stats?.today_tasks ?? 0}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-green-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">活跃Agent数</p>
                    <p className="text-2xl font-bold">{stats?.active_agents ?? 0}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
                    <Target className="w-5 h-5 text-amber-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">新增线索</p>
                    <p className="text-2xl font-bold">{stats?.new_clues ?? 0}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                    <AlertCircle className="w-5 h-5 text-purple-500" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">待审核</p>
                    <p className="text-2xl font-bold">{stats?.pending_review ?? 0}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* 场景快捷入口 */}
      <div>
        <h2 className="text-lg font-semibold mb-4">营销场景</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {SCENE_CARDS.map((scene) => {
            const Icon = scene.icon;
            return (
              <Card
                key={scene.code}
                className="group hover:shadow-md transition-all cursor-pointer border-border/50 hover:border-primary/50"
                onClick={() => handleSceneStart(scene.code)}
              >
                <CardContent className="p-5 flex items-start gap-4">
                  <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center shrink-0", scene.bg)}>
                    <Icon className={cn("w-6 h-6", scene.color)} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-base mb-1">{scene.name}</h3>
                    <p className="text-sm text-muted-foreground mb-3">{scene.description}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="group-hover:bg-primary group-hover:text-primary-foreground transition-colors"
                    >
                      开始 <ArrowRight className="w-3 h-3 ml-1" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* 最近任务 + 快捷导航 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 最近任务 */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">最近任务</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate('/vmd/tasks')}>
                查看全部 <ArrowRight className="w-3 h-3 ml-1" />
              </Button>
            </CardHeader>
            <CardContent>
              {tasksLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 w-full" />
                  ))}
                </div>
              ) : recentTasks.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <ListTodo className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p>暂无任务，开始创建您的第一个营销任务吧</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentTasks.map((task) => {
                    const statusCfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
                    return (
                      <div
                        key={task.id}
                        className="flex items-center gap-4 p-3 rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                        onClick={() => navigate(`/vmd/tasks?detail=${task.id}`)}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs text-muted-foreground font-mono">{task.task_code}</span>
                            <Badge className={cn("text-[10px]", statusCfg.color)}>
                              {statusCfg.label}
                            </Badge>
                          </div>
                          <p className="text-sm font-medium truncate">{task.title}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <Badge variant="outline" className="text-[10px]">
                            {SCENE_NAMES[task.scene_code] || task.scene_code}
                          </Badge>
                          <div className="mt-1">
                            <Progress value={task.progress} className="h-1.5 w-20" />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 快捷导航 */}
        <div>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">快捷导航</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2">
                {QUICK_NAV.map((nav) => {
                  const Icon = nav.icon;
                  return (
                    <Button
                      key={nav.path}
                      variant="outline"
                      className="h-auto py-3 flex flex-col items-center gap-1.5 hover:bg-primary/5 hover:border-primary/30"
                      onClick={() => navigate(nav.path)}
                    >
                      <Icon className="w-5 h-5 text-muted-foreground" />
                      <span className="text-xs">{nav.label}</span>
                    </Button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

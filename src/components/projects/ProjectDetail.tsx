import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Avatar } from '@/components/ui/avatar';
import {
    ArrowLeft, Calendar, CheckCircle2, Clock, Flag, Users, MessageSquare,
    Utensils, Zap, ListTodo, Loader2, Plus, X, ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
    useProjectDetail, useOrgMembers, useUpdateProjectMembers,
    useUpdateProjectStage, useAddTimelineEvent, useAiAnalyzeProgress,
    useRecalcProgress, useAiPredictNextStep, useGenerateWeeklyReport, STAGE_OPTIONS, EVENT_TYPE_OPTIONS,
    TeamMember, ProjectTimeline,
} from '@/hooks/useProjects';
import { ProjectTask } from '@/types/nexus';
import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useUser } from '@/contexts/UserContext';
import { httpClient } from '@/lib/httpClient';
import { useNavigate, useParams } from 'react-router-dom';
import type { Database } from '@/integrations/supabase/types';
import { toast } from 'sonner';
import { NoDataYet } from '@/components/common/EmptyState';

interface ProjectDetailProps {
    projectId?: string;
    onBack?: () => void;
}

export function ProjectDetail({ projectId: propId, onBack: propOnBack }: ProjectDetailProps) {
    const { id: paramId } = useParams();
    const navigate = useNavigate();
    const { user } = useUser();

    const projectId = propId || paramId || '';
    const onBack = propOnBack || (() => navigate(-1));

    const { project, timeline, loading, refresh } = useProjectDetail(projectId);

    // ── Members Dialog ──
    const [membersOpen, setMembersOpen] = useState(false);
    const { data: orgMembers = [] } = useOrgMembers();
    const updateMembers = useUpdateProjectMembers();
    const [selectedMemberIds, setSelectedMemberIds] = useState<string[]>([]);

    const openMembersDialog = () => {
        const currentIds = project?.member_ids || [];
        setSelectedMemberIds(currentIds);
        setMembersOpen(true);
    };

    const toggleMember = (userId: string) => {
        setSelectedMemberIds(prev =>
            prev.includes(userId) ? prev.filter(id => id !== userId) : [...prev, userId]
        );
    };

    const saveMemberIds = async () => {
        await updateMembers.mutateAsync({ projectId, memberIds: selectedMemberIds });
        setMembersOpen(false);
        refresh();
    };

    // ── AI Analysis Dialog ──
    const [aiDialogOpen, setAiDialogOpen] = useState(false);
    const { analyze, analyzing, result: aiResult, clearResult } = useAiAnalyzeProgress();

    // ── Weekly Report ──
    const [reportDialogOpen, setReportDialogOpen] = useState(false);
    const weeklyReport = useGenerateWeeklyReport();

    const { data: subtasks = [] } = useQuery<ProjectTask[]>({
        queryKey: ['project-subtasks', projectId],
        queryFn: async () => {
            const response = await (httpClient as { get: (url: string) => Promise<{ data: { tasks?: ProjectTask[] } }> }).get(`/api/projects/${projectId}/tasks`);
            return response.data?.tasks || [];
        },
        enabled: !!projectId,
    });

    const handleAiAnalyze = () => {
        if (!project) return;
        setAiDialogOpen(true);
        analyze(project, timeline, subtasks.map((t: ProjectTask) => ({ title: t.title, status: t.status })));
    };

    // ── Stage Transition ──
    const updateStage = useUpdateProjectStage();
    const handleStageChange = async (newStage: string) => {
        if (!project || newStage === project.stage) return;
        await updateStage.mutateAsync({ projectId, stage: newStage, userId: user.id });
        refresh();
    };

    // ── Add Timeline Event ──
    const [addEventOpen, setAddEventOpen] = useState(false);
    const [newEvent, setNewEvent] = useState({ title: '', content: '', event_type: 'meeting' });
    const addEvent = useAddTimelineEvent();

    const handleAddEvent = async () => {
        if (!newEvent.title.trim()) { toast.error('请输入事件标题'); return; }
        await addEvent.mutateAsync({
            project_id: projectId,
            title: newEvent.title,
            content: newEvent.content,
            event_type: newEvent.event_type,
            created_by: user.id,
        });
        setNewEvent({ title: '', content: '', event_type: 'meeting' });
        setAddEventOpen(false);
        refresh();
    };

    // ── Recalc Progress ──
    const recalcProgress = useRecalcProgress();

    // ── AI Predict Next Step ──
    const { predict, predicting, prediction } = useAiPredictNextStep();

    if (!projectId) return <div>Error: Project ID missing</div>;

    if (loading || !project) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full" />
            </div>
        );
    }

    const memberIds: string[] = project?.member_ids || [];
    const memberProfiles = orgMembers.filter((m: TeamMember) => memberIds.includes(m.user_id));

    const getEventIcon = (type: string) => {
        switch (type) {
            case 'milestone': return <Flag className="w-4 h-4" />;
            case 'meeting': return <MessageSquare className="w-4 h-4" />;
            case 'dinner': return <Utensils className="w-4 h-4" />;
            case 'task': return <CheckCircle2 className="w-4 h-4" />;
            default: return <Clock className="w-4 h-4" />;
        }
    };

    const getEventColor = (type: string) => {
        switch (type) {
            case 'milestone': return 'bg-gold/20 text-gold border-gold/30';
            case 'meeting': return 'bg-primary/20 text-primary border-primary/30';
            case 'dinner': return 'bg-purple-500/20 text-purple-500 border-purple-500/30';
            case 'task': return 'bg-success/20 text-success border-success/30';
            default: return 'bg-muted/20 text-muted-foreground border-muted/30';
        }
    };

    return (
        <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={onBack} className="rounded-full">
                        <ArrowLeft className="w-5 h-5" />
                    </Button>
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <span className="px-2 py-0.5 text-[10px] rounded-full font-medium uppercase bg-primary/10 text-primary">
                                {project.type}
                            </span>
                            <span className="text-xs text-muted-foreground">创建于 {project.created_at ? new Date(project.created_at).toLocaleDateString() : '未知'}</span>
                        </div>
                        <h1 className="text-2xl font-bold text-foreground">{project.name}</h1>
                    </div>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={openMembersDialog}>
                        <Users className="w-4 h-4 mr-2" />
                        参与人员{memberIds.length > 0 && ` (${memberIds.length})`}
                    </Button>
                    <Button variant="premium" size="sm" onClick={handleAiAnalyze} disabled={analyzing}>
                        {analyzing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Zap className="w-4 h-4 mr-2" />}
                        AI 分析进度
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => { setReportDialogOpen(true); weeklyReport.mutate(projectId); }} disabled={weeklyReport.isPending}>
                        {weeklyReport.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Flag className="w-4 h-4 mr-2" />}
                        AI 周报
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column: Stats & Description */}
                <div className="lg:col-span-1 space-y-6">
                    <div className="bg-card rounded-2xl p-6 border border-border shadow-sm">
                        <h3 className="text-sm font-semibold mb-4 text-foreground/70 uppercase tracking-wider">项目现状</h3>
                        <div className="space-y-4">
                            {/* Stage Selector */}
                            <div>
                                <div className="flex justify-between text-sm mb-2">
                                    <span className="text-muted-foreground">当前阶段</span>
                                </div>
                                <Select value={project.stage} onValueChange={handleStageChange} disabled={updateStage.isPending}>
                                    <SelectTrigger className="w-full">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {STAGE_OPTIONS.map(opt => (
                                            <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Progress */}
                            <div>
                                <div className="flex justify-between text-sm mb-2">
                                    <span className="text-muted-foreground">进度完成率</span>
                                    <span className="font-semibold text-foreground">{project.progress}%</span>
                                </div>
                                <div className="h-3 w-full bg-secondary rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-gradient-to-r from-primary to-primary/60 rounded-full transition-all duration-1000"
                                        style={{ width: `${project.progress}%` }}
                                    />
                                </div>
                                {subtasks.length > 0 && (
                                    <button
                                        className="text-xs text-primary hover:underline mt-1"
                                        onClick={async () => {
                                            await recalcProgress.mutateAsync(projectId);
                                            refresh();
                                            toast.success('进度已根据任务完成率重新计算');
                                        }}
                                    >
                                        根据任务自动计算
                                    </button>
                                )}
                            </div>

                            {/* Members Preview */}
                            {memberProfiles.length > 0 && (
                                <div>
                                    <span className="text-sm text-muted-foreground block mb-2">参与人员</span>
                                    <div className="flex flex-wrap gap-1">
                                        {memberProfiles.map((member: TeamMember) => (
                                            <Avatar key={member.user_id} className="h-8 w-8 border-2 border-background">
                                                <div className="w-full h-full flex items-center justify-center bg-muted text-xs font-medium">
                                                    {member.name?.slice(0, 1)}
                                                </div>
                                            </Avatar>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="bg-card rounded-2xl p-6 border border-border shadow-sm">
                        <h3 className="text-sm font-semibold mb-3 text-foreground/70 uppercase tracking-wider">项目简介</h3>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                            {project.description}
                        </p>
                    </div>
                </div>

                {/* Right Column: Waterfall Timeline */}
                <div className="lg:col-span-2">
                    <div className="bg-card rounded-3xl p-8 border border-border shadow-sm relative overflow-hidden">
                        <div className="flex items-center justify-between mb-8">
                            <h3 className="text-lg font-bold text-foreground">进展流 (Waterfall Flow)</h3>
                            <div className="flex items-center gap-3">
                                <div className="flex gap-2">
                                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                        <div className="w-2 h-2 rounded-full bg-gold"></div> 关键节点
                                    </div>
                                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                        <div className="w-2 h-2 rounded-full bg-primary"></div> 日常活动
                                    </div>
                                </div>
                                <Button variant="outline" size="sm" onClick={() => setAddEventOpen(true)}>
                                    <Plus className="w-3 h-3 mr-1" /> 添加记录
                                </Button>
                            </div>
                        </div>

                        <div className="relative">
                            {/* Vertical Line */}
                            <div className="absolute left-[19px] top-2 bottom-0 w-0.5 bg-gradient-to-b from-primary/30 via-border to-transparent" />

                            <div className="space-y-10">
                                {timeline.length === 0 ? (
                                    <NoDataYet
                                        title="暂无进展记录"
                                        description="点击右上角「添加记录」开始记录项目进展"
                                        className="py-8"
                                    />
                                ) : timeline.map((event: ProjectTimeline) => (
                                    <div key={event.id} className="relative pl-12 group">
                                        <div className={cn(
                                            "absolute left-0 top-0 w-10 h-10 rounded-xl border-2 flex items-center justify-center bg-card shadow-sm z-10 transition-all duration-300 group-hover:scale-110",
                                            getEventColor(event.event_type)
                                        )}>
                                            {getEventIcon(event.event_type)}
                                        </div>

                                        <div className="space-y-2">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <h4 className="font-bold text-foreground">{event.title}</h4>
                                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground uppercase">
                                                        {event.event_type}
                                                    </span>
                                                </div>
                                                <span className="text-xs text-muted-foreground flex items-center gap-1">
                                                    <Clock className="w-3 h-3" />
                                                    {new Date(event.occurred_at || Date.now()).toLocaleDateString()}
                                                </span>
                                            </div>
                                            <div className="bg-secondary/30 rounded-xl p-4 border border-border/50 group-hover:border-primary/30 transition-colors">
                                                <p className="text-sm text-muted-foreground leading-relaxed">
                                                    {event.content}
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                ))}

                                {/* AI Predict Next Step */}
                                <div className="relative pl-12">
                                    <div className="absolute left-[13px] top-1 w-3 h-3 rounded-full border-2 border-dashed border-primary bg-card" />
                                    <div className="space-y-2">
                                        {prediction ? (
                                            <>
                                                <h4 className="text-sm font-medium text-primary flex items-center gap-1">
                                                    <Zap className="w-3 h-3" /> AI 预测下一步
                                                </h4>
                                                <p className="text-xs text-muted-foreground italic">{prediction}</p>
                                            </>
                                        ) : predicting ? (
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                <Loader2 className="w-3 h-3 animate-spin" /> AI 正在预测下一个节点...
                                            </div>
                                        ) : (
                                            <button
                                                className="text-xs text-primary hover:underline flex items-center gap-1"
                                                onClick={() => project && predict(project, timeline)}
                                            >
                                                <Zap className="w-3 h-3" /> 点击让 AI 预测下一个节点
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Subtask List */}
                    <ProjectSubtasks projectId={projectId} tasks={subtasks} onProgressChange={async () => {
                        await recalcProgress.mutateAsync(projectId);
                        refresh();
                    }} />
                </div>
            </div>

            {/* ── Members Dialog ── */}
            <Dialog open={membersOpen} onOpenChange={setMembersOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>管理参与人员</DialogTitle>
                    </DialogHeader>
                    <div className="max-h-80 overflow-y-auto space-y-1">
                        {orgMembers.map((member: TeamMember) => (
                            <label
                                key={member.user_id}
                                className={cn(
                                    "flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors",
                                    selectedMemberIds.includes(member.user_id) ? "bg-primary/10 border border-primary/30" : "hover:bg-muted border border-transparent"
                                )}
                            >
                                <input
                                    type="checkbox"
                                    checked={selectedMemberIds.includes(member.user_id)}
                                    onChange={() => toggleMember(member.user_id)}
                                    className="rounded"
                                />
                                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-xs font-medium text-primary">
                                    {member.name?.slice(0, 1)}
                                </div>
                                <div className="flex-1">
                                    <div className="text-sm font-medium">{member.name}</div>
                                    <div className="text-xs text-muted-foreground">{member.department}</div>
                                </div>
                            </label>
                        ))}
                        {orgMembers.length === 0 && (
                            <NoDataYet title="暂无团队成员" description="组织内暂无可添加的成员" className="py-6" />
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setMembersOpen(false)}>取消</Button>
                        <Button onClick={saveMemberIds} disabled={updateMembers.isPending}>
                            {updateMembers.isPending ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                            保存
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* ── AI Analysis Dialog ── */}
            <Dialog open={aiDialogOpen} onOpenChange={(open) => { setAiDialogOpen(open); if (!open) clearResult(); }}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Zap className="w-5 h-5 text-primary" /> AI 进度分析
                        </DialogTitle>
                    </DialogHeader>
                    <div className="min-h-[120px]">
                        {analyzing ? (
                            <div className="flex flex-col items-center justify-center py-8 gap-3">
                                <Loader2 className="w-8 h-8 animate-spin text-primary" />
                                <span className="text-sm text-muted-foreground">AI 正在分析项目进展...</span>
                            </div>
                        ) : aiResult ? (
                            <div className="text-sm text-foreground leading-relaxed whitespace-pre-wrap bg-muted/30 rounded-lg p-4">
                                {aiResult}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-sm text-muted-foreground">等待分析结果...</div>
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setAiDialogOpen(false)}>关闭</Button>
                        {!analyzing && aiResult && (
                            <Button onClick={() => {
                                if (project) analyze(project, timeline, subtasks.map((t: ProjectTask) => ({ title: t.title, status: t.status })));
                            }}>
                                重新分析
                            </Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* ── Weekly Report Dialog ── */}
            <Dialog open={reportDialogOpen} onOpenChange={setReportDialogOpen}>
                <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Flag className="w-5 h-5 text-primary" /> AI 项目周报
                        </DialogTitle>
                    </DialogHeader>
                    <div className="min-h-[120px]">
                        {weeklyReport.isPending ? (
                            <div className="flex flex-col items-center justify-center py-8 gap-3">
                                <Loader2 className="w-8 h-8 animate-spin text-primary" />
                                <span className="text-sm text-muted-foreground">AI 正在生成周报...</span>
                            </div>
                        ) : weeklyReport.data?.report ? (
                            <div className="text-sm text-foreground leading-relaxed whitespace-pre-wrap bg-muted/30 rounded-lg p-4">
                                {weeklyReport.data.report}
                            </div>
                        ) : weeklyReport.isError ? (
                            <div className="text-center py-8 text-sm text-destructive">周报生成失败，请重试</div>
                        ) : (
                            <div className="text-center py-8 text-sm text-muted-foreground">等待生成...</div>
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setReportDialogOpen(false)}>关闭</Button>
                        {!weeklyReport.isPending && (
                            <Button onClick={() => weeklyReport.mutate(projectId)}>重新生成</Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* ── Add Event Dialog ── */}
            <Dialog open={addEventOpen} onOpenChange={setAddEventOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>添加进展记录</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div>
                            <label className="text-sm font-medium mb-1 block">事件类型</label>
                            <Select value={newEvent.event_type} onValueChange={v => setNewEvent(prev => ({ ...prev, event_type: v }))}>
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    {EVENT_TYPE_OPTIONS.map(opt => (
                                        <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <label className="text-sm font-medium mb-1 block">标题</label>
                            <Input
                                placeholder="例如：与客户确认需求范围"
                                value={newEvent.title}
                                onChange={e => setNewEvent(prev => ({ ...prev, title: e.target.value }))}
                            />
                        </div>
                        <div>
                            <label className="text-sm font-medium mb-1 block">详细内容</label>
                            <Textarea
                                placeholder="记录具体内容..."
                                rows={3}
                                value={newEvent.content}
                                onChange={e => setNewEvent(prev => ({ ...prev, content: e.target.value }))}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setAddEventOpen(false)}>取消</Button>
                        <Button onClick={handleAddEvent} disabled={addEvent.isPending}>
                            {addEvent.isPending ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
                            添加
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

/* ────────────────── Project Subtasks ────────────────── */

const taskStatusConfig: Record<string, { label: string; color: string }> = {
    pending: { label: '待处理', color: 'text-yellow-500 bg-yellow-500/10' },
    todo: { label: '待处理', color: 'text-yellow-500 bg-yellow-500/10' },
    in_progress: { label: '进行中', color: 'text-blue-500 bg-blue-500/10' },
    done: { label: '已完成', color: 'text-green-500 bg-green-500/10' },
    completed: { label: '已完成', color: 'text-green-500 bg-green-500/10' },
    cancelled: { label: '已取消', color: 'text-gray-500 bg-gray-500/10' },
};

const priorityConfig: Record<string, { label: string; color: string }> = {
    urgent: { label: '紧急', color: 'text-red-600' },
    high: { label: '高', color: 'text-red-500' },
    medium: { label: '中', color: 'text-yellow-500' },
    low: { label: '低', color: 'text-green-500' },
};

function ProjectSubtasks({ projectId, tasks, onProgressChange }: {
    projectId: string;
    tasks: ProjectTask[];
    onProgressChange: () => void;
}) {
    const navigate = useNavigate();

    const handleStatusToggle = async (task: ProjectTask) => {
        const newStatus = (task.status === 'done' || task.status === 'completed') ? 'todo' : 'done';
        const { error } = await (supabase.from('oa_tasks') as unknown as { update: (data: Record<string, unknown>) => { eq: (col: string, val: unknown) => Promise<{ error: unknown }> } })
            .update({ status: newStatus })
            .eq('id', task.id);
        if (error) { toast.error('更新任务状态失败'); return; }
        toast.success(newStatus === 'done' ? '任务已完成' : '任务已重新打开');
        onProgressChange();
    };

    return (
        <div className="bg-card rounded-2xl p-6 border border-border shadow-sm mt-6">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                    <ListTodo className="w-5 h-5" />
                    关联任务
                </h3>
                <div className="flex items-center gap-2">
                    <Badge variant="outline">{tasks.length} 项</Badge>
                    {tasks.length > 0 && (
                        <Badge variant="outline" className="text-green-600">
                            {tasks.filter(t => t.status === 'done' || t.status === 'completed').length} 已完成
                        </Badge>
                    )}
                </div>
            </div>

            {tasks.length === 0 ? (
                <NoDataYet
                    title="暂无关联任务"
                    description="可通过 AI 助手创建项目任务"
                    className="py-6 border border-dashed rounded-lg"
                />
            ) : (
                <div className="space-y-2">
                    {tasks.map(task => {
                        const status = taskStatusConfig[task.status] || taskStatusConfig.todo;
                        const priority = priorityConfig[task.priority] || priorityConfig.medium;
                        const isDone = task.status === 'done' || task.status === 'completed';
                        return (
                            <div
                                key={task.id}
                                className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors cursor-pointer group"
                            >
                                <div className="flex items-center gap-3">
                                    <button
                                        onClick={(e) => { e.stopPropagation(); handleStatusToggle(task); }}
                                        className="flex-shrink-0"
                                    >
                                        <CheckCircle2 className={cn(
                                            'w-5 h-5 transition-colors',
                                            isDone ? 'text-green-500' : 'text-muted-foreground/40 hover:text-green-400'
                                        )} />
                                    </button>
                                    <span
                                        className={cn('text-sm font-medium cursor-pointer hover:text-primary', isDone && 'line-through text-muted-foreground')}
                                        onClick={() => navigate(`/tasks?id=${task.id}`)}
                                    >
                                        {task.title}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className={cn('text-xs', priority.color)}>{priority.label}</span>
                                    <Badge className={cn('text-xs', status.color)}>{status.label}</Badge>
                                    <ChevronRight className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

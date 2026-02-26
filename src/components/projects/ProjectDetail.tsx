import React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
    ArrowLeft,
    Calendar,
    CheckCircle2,
    Clock,
    Flag,
    Users,
    MessageSquare,
    Utensils,
    ChevronRight,
    Zap,
    MoreVertical,
    ListTodo,
    Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useProjectDetail, ProjectTimeline } from '@/hooks/useProjects';
import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';

import { useNavigate, useParams } from 'react-router-dom';

interface ProjectDetailProps {
    projectId?: string;
    onBack?: () => void;
}

export function ProjectDetail({ projectId: propId, onBack: propOnBack }: ProjectDetailProps) {
    const { id: paramId } = useParams();
    const navigate = useNavigate();

    // Prioritize prop (if embedded) -> param
    const projectId = propId || paramId || '';
    const onBack = propOnBack || (() => navigate(-1));

    const { project, timeline, loading } = useProjectDetail(projectId);

    // Ensure we have an ID
    if (!projectId) {
        return <div>Error: Project ID missing</div>;
    }

    if (loading || !project) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full" />
            </div>
        );
    }

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
                            <span className="text-xs text-muted-foreground">创建于 {new Date(project.created_at).toLocaleDateString()}</span>
                        </div>
                        <h1 className="text-2xl font-bold text-foreground">{project.name}</h1>
                    </div>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm">
                        <Users className="w-4 h-4 mr-2" />
                        参与人员
                    </Button>
                    <Button variant="premium" size="sm">
                        <Zap className="w-4 h-4 mr-2" />
                        AI 分析进度
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column: Stats & Description */}
                <div className="lg:col-span-1 space-y-6">
                    <div className="bg-card rounded-2xl p-6 border border-border shadow-sm">
                        <h3 className="text-sm font-semibold mb-4 text-foreground/70 uppercase tracking-wider">项目现状</h3>
                        <div className="space-y-4">
                            <div>
                                <div className="flex justify-between text-sm mb-2">
                                    <span className="text-muted-foreground">当前阶段</span>
                                    <span className="font-semibold text-primary">{project.stage}</span>
                                </div>
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
                            </div>
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
                            <div className="flex gap-2">
                                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <div className="w-2 h-2 rounded-full bg-gold"></div> 关键节点
                                </div>
                                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <div className="w-2 h-2 rounded-full bg-primary"></div> 日常活动
                                </div>
                            </div>
                        </div>

                        <div className="relative">
                            {/* Vertical Line */}
                            <div className="absolute left-[19px] top-2 bottom-0 w-0.5 bg-gradient-to-b from-primary/30 via-border to-transparent" />

                            <div className="space-y-10">
                                {timeline.map((event, idx) => (
                                    <div key={event.id} className="relative pl-12 group">
                                        {/* Node Dot */}
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
                                                    {new Date(event.occurred_at).toLocaleDateString()}
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

                                {/* Next Step Placeholder */}
                                <div className="relative pl-12 opacity-50">
                                    <div className="absolute left-[13px] top-1 w-3 h-3 rounded-full border-2 border-dashed border-primary bg-card" />
                                    <div className="space-y-2">
                                        <h4 className="text-sm font-medium text-muted-foreground">AI 预测下一个节点...</h4>
                                        <p className="text-xs text-muted-foreground italic">"建议在完成环境预检后，安排一次与客户运维团队的正式会议。"</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* AI Command Instruction */}
                        <div className="mt-12 p-4 bg-primary/5 border border-primary/20 rounded-2xl flex items-start gap-4">
                            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                                <Zap className="w-5 h-5 text-primary" />
                            </div>
                            <div className="flex-1">
                                <h4 className="text-sm font-bold text-foreground mb-1">AI 提议制成中</h4>
                                <p className="text-xs text-muted-foreground">
                                    您可以直接在下方 AI 指挥中心输入：<span className="text-primary font-medium">"在项目达成阶段帮我创建一个请客吃饭的事件，地点在北京路"</span>，AI 将为您自动记录并安排。
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Subtask List */}
                    <ProjectSubtasks projectId={projectId} />
                </div>
            </div>
        </div>
    );
}

/* ────────────────── Project Subtasks ────────────────── */
interface OATask {
    id: string;
    title: string;
    status: string;
    priority: string;
    assignee_id: string | null;
    created_at: string;
}

const taskStatusConfig: Record<string, { label: string; color: string }> = {
    pending: { label: '待处理', color: 'text-yellow-500 bg-yellow-500/10' },
    in_progress: { label: '进行中', color: 'text-blue-500 bg-blue-500/10' },
    completed: { label: '已完成', color: 'text-green-500 bg-green-500/10' },
    cancelled: { label: '已取消', color: 'text-gray-500 bg-gray-500/10' },
};

const priorityConfig: Record<string, { label: string; color: string }> = {
    high: { label: '高', color: 'text-red-500' },
    medium: { label: '中', color: 'text-yellow-500' },
    low: { label: '低', color: 'text-green-500' },
};

function ProjectSubtasks({ projectId }: { projectId: string }) {
    const { data: tasks = [], isLoading } = useQuery({
        queryKey: ['project-subtasks', projectId],
        queryFn: async () => {
            const { data, error } = await supabase.from('oa_tasks')
                .select('id, title, status, priority, assignee_id, created_at')
                .eq('metadata->>project_id', projectId)
                .order('created_at', { ascending: false })
                .limit(20);

            if (error) throw error;
            return (data || []) as OATask[];
        },
        enabled: !!projectId,
    });

    return (
        <div className="bg-card rounded-2xl p-6 border border-border shadow-sm mt-6">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                    <ListTodo className="w-5 h-5" />
                    关联任务
                </h3>
                <Badge variant="outline">{tasks.length} 项</Badge>
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                </div>
            ) : tasks.length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground border border-dashed rounded-lg">
                    暂无关联任务，可通过 AI 助手创建项目任务
                </div>
            ) : (
                <div className="space-y-2">
                    {tasks.map(task => {
                        const status = taskStatusConfig[task.status] || taskStatusConfig.pending;
                        const priority = priorityConfig[task.priority] || priorityConfig.medium;
                        return (
                            <div key={task.id} className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors">
                                <div className="flex items-center gap-3">
                                    <CheckCircle2 className={cn('w-4 h-4', task.status === 'completed' ? 'text-green-500' : 'text-muted-foreground')} />
                                    <span className={cn('text-sm font-medium', task.status === 'completed' && 'line-through text-muted-foreground')}>
                                        {task.title}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className={cn('text-xs', priority.color)}>{priority.label}</span>
                                    <Badge className={cn('text-xs', status.color)}>{status.label}</Badge>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

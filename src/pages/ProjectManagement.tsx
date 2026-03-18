import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Bot, Plus, Briefcase, Calendar, ChevronRight, Loader2, Trash2, LayoutGrid, Columns3 } from "lucide-react";
import { useUser } from "@/contexts/UserContext";
import { supabase } from "@/integrations/supabase/client";
import { getApiBaseUrl } from '@/lib/apiConfig';
import { toast } from "sonner";
import { useAuth } from "@/components/auth/AuthContext";
import { useDeleteProject, STAGE_OPTIONS } from "@/hooks/useProjects";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";

interface Project {
    id: string;
    name: string;
    description: string;
    stage: 'planning' | 'in_progress' | 'completed' | 'on_hold';
    progress: number;
    created_at: string;
    owner_id: string;
}

type ViewMode = 'grid' | 'kanban';

export function ProjectManagement() {
    const { user } = useUser();
    const navigate = useNavigate();
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [aiPrompt, setAiPrompt] = useState("");
    const [isAiCreating, setIsAiCreating] = useState(false);
    const [viewMode, setViewMode] = useState<ViewMode>('grid');
    const { role } = useAuth();
    const canDelete = role === 'boss' || role === 'admin';
    const deleteProject = useDeleteProject();
    const { confirm, ConfirmDialogProps } = useConfirmDialog();

    const fetchProjects = useCallback(async () => {
        try {
            if (!user) return;
            const query = supabase
                .from('projects')
                .select('*')
                .neq('stage', 'archived')
                .order('created_at', { ascending: false });

            if (user.role !== 'boss' && user.role !== 'admin') {
                query.eq('user_id', user.id);
            }

            const { data, error } = await query;
            if (error) throw error;
            setProjects(data as Project[] || []);
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } catch (error: any) {
            toast.error(error?.message || "加载项目失败");
        } finally {
            setLoading(false);
        }
    }, [user]);

    useEffect(() => {
        fetchProjects();

        const channel = supabase
            .channel('projects-changes')
            .on('postgres_changes', {
                event: '*',
                schema: 'public',
                table: 'projects',
                filter: user?.role === 'boss' ? undefined : `user_id=eq.${user?.id}`,
            }, () => {
                fetchProjects();
            })
            .subscribe();

        return () => { supabase.removeChannel(channel); };
    }, [user, fetchProjects]);

    const handleAiCreate = async () => {
        if (!aiPrompt.trim()) return;
        setIsAiCreating(true);

        try {
            const endpoint = `${getApiBaseUrl()}/api/chat`;
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token ? `Bearer ${token}` : ''
                },
                body: JSON.stringify({
                    messages: [
                        { role: "system", content: "You are an expert Project Manager AI. Access the 'create_project' tool immediately to fulfill this request. Do not ask for confirmation, just do it based on valid assumptions." },
                        { role: "user", content: `帮我创建一个项目，需求是：${aiPrompt}` }
                    ],
                    model: "gpt-4o",
                    agent: "default"
                })
            });

            if (!response.ok) throw new Error("AI Request Failed");

            const reader = response.body?.getReader();
            if (reader) {
                while (true) {
                    const { done } = await reader.read();
                    if (done) break;
                }
            }

            toast.success("AI 已接收指令并开始处理，请稍候...", {
                description: "项目创建成功后将自动出现在列表中"
            });
            setAiPrompt("");
            await fetchProjects();
            toast.success("项目列表已刷新");
        } catch {
            toast.error("AI 服务连接失败，请稍后重试");
        } finally {
            setIsAiCreating(false);
        }
    };

    const handleDeleteProject = async (e: React.MouseEvent, project: Project) => {
        e.stopPropagation();
        const ok = await confirm({
            title: '确认删除项目',
            description: `确定要删除项目「${project.name}」吗？项目将被归档。`,
            variant: 'destructive',
            confirmText: '删除',
        });
        if (ok) {
            await deleteProject.mutateAsync(project.id);
            await fetchProjects();
        }
    };

    const handleStageChange = async (projectId: string, newStage: string) => {
        const { error } = await supabase
            .from('projects')
            .update({ stage: newStage } as never)
            .eq('id', projectId);
        if (error) { toast.error('更新阶段失败'); return; }
        toast.success('阶段已更新');
        fetchProjects();
    };

    const getStatusBadge = (stage: string) => {
        switch (stage) {
            case 'in_progress': return <Badge variant="default" className="bg-blue-500">进行中</Badge>;
            case 'completed': return <Badge variant="default" className="bg-green-500">已完成</Badge>;
            case 'on_hold': return <Badge variant="secondary">已暂停</Badge>;
            default: return <Badge variant="outline">规划中</Badge>;
        }
    };

    // ── Stats ──
    const stats = {
        total: projects.length,
        planning: projects.filter(p => p.stage === 'planning').length,
        in_progress: projects.filter(p => p.stage === 'in_progress').length,
        completed: projects.filter(p => p.stage === 'completed').length,
        on_hold: projects.filter(p => p.stage === 'on_hold').length,
        avgProgress: projects.length > 0 ? Math.round(projects.reduce((sum, p) => sum + (p.progress || 0), 0) / projects.length) : 0,
        completionRate: projects.length > 0 ? Math.round((projects.filter(p => p.stage === 'completed').length / projects.length) * 100) : 0,
    };

    const renderProjectCard = (project: Project) => (
        <Card
            key={project.id}
            onClick={() => navigate(`/projects/${project.id}`)}
            className="group hover:shadow-lg transition-all border-border/50 hover:border-primary/50 cursor-pointer overflow-hidden relative"
        >
            <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-primary to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                    <div className="space-y-1">
                        <CardTitle className="text-lg leading-tight flex items-center gap-2">
                            {project.name}
                        </CardTitle>
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Calendar className="w-3 h-3" /> {new Date(project.created_at).toLocaleDateString()}
                        </span>
                    </div>
                    {getStatusBadge(project.stage)}
                </div>
            </CardHeader>
            <CardContent>
                <p className="text-sm text-muted-foreground line-clamp-2 mb-4 h-10">
                    {project.description || "暂无描述"}
                </p>

                <div className="space-y-1">
                    <div className="flex justify-between text-xs text-muted-foreground">
                        <span>完成进度</span>
                        <span>{project.progress}%</span>
                    </div>
                    <Progress value={project.progress} className="h-2" />
                </div>

                <div className="mt-4 pt-4 border-t border-border/50 flex items-center justify-end text-xs text-muted-foreground">
                    <div className="flex items-center gap-1">
                        {canDelete && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-2 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                                onClick={(e) => handleDeleteProject(e, project)}
                            >
                                <Trash2 className="w-3 h-3" />
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 hover:text-primary"
                            onClick={(e) => { e.stopPropagation(); navigate(`/projects/${project.id}`); }}
                        >
                            详情 <ChevronRight className="w-3 h-3 ml-1" />
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );

    return (
        <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
            <div className="flex items-center justify-between">
                <div className="flex flex-col gap-2">
                    <h1 className="text-2xl font-bold tracking-tight">项目管理</h1>
                    <p className="text-muted-foreground">全生命周期项目追踪与协作</p>
                </div>
                {projects.length > 0 && (
                    <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
                        <Button
                            variant={viewMode === 'grid' ? 'default' : 'ghost'}
                            size="sm"
                            className="h-8 px-3"
                            onClick={() => setViewMode('grid')}
                        >
                            <LayoutGrid className="w-4 h-4 mr-1" /> 卡片
                        </Button>
                        <Button
                            variant={viewMode === 'kanban' ? 'default' : 'ghost'}
                            size="sm"
                            className="h-8 px-3"
                            onClick={() => setViewMode('kanban')}
                        >
                            <Columns3 className="w-4 h-4 mr-1" /> 看板
                        </Button>
                    </div>
                )}
            </div>

            {/* Stats Dashboard */}
            {projects.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                    {[
                        { label: '全部项目', count: stats.total, color: 'text-foreground', bg: 'bg-card' },
                        { label: '规划中', count: stats.planning, color: 'text-gray-500', bg: 'bg-gray-500/5' },
                        { label: '进行中', count: stats.in_progress, color: 'text-blue-500', bg: 'bg-blue-500/5' },
                        { label: '已完成', count: stats.completed, color: 'text-green-500', bg: 'bg-green-500/5' },
                        { label: '已暂停', count: stats.on_hold, color: 'text-yellow-500', bg: 'bg-yellow-500/5' },
                    ].map(s => (
                        <div key={s.label} className={cn("rounded-xl p-3 border border-border text-center", s.bg)}>
                            <div className={cn("text-2xl font-bold", s.color)}>{s.count}</div>
                            <div className="text-xs text-muted-foreground">{s.label}</div>
                        </div>
                    ))}
                    <div className="rounded-xl p-3 border border-border text-center bg-primary/5">
                        <div className="text-2xl font-bold text-primary">{stats.avgProgress}%</div>
                        <div className="text-xs text-muted-foreground">平均进度</div>
                        <Progress value={stats.avgProgress} className="h-1 mt-1.5" />
                    </div>
                    <div className="rounded-xl p-3 border border-border text-center bg-green-500/5">
                        <div className="text-2xl font-bold text-green-600">{stats.completionRate}%</div>
                        <div className="text-xs text-muted-foreground">完成率</div>
                        <Progress value={stats.completionRate} className="h-1 mt-1.5" />
                    </div>
                </div>
            )}

            {/* AI Quick Action */}
            <Card className="bg-gradient-to-r from-primary/10 to-transparent border-primary/20">
                <CardContent className="p-6 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center text-primary shrink-0">
                        <Bot className="w-6 h-6" />
                    </div>
                    <div className="flex-1">
                        <h3 className="text-lg font-semibold text-primary mb-1">AI 智能立项助手</h3>
                        <p className="text-sm text-muted-foreground mb-3">
                            只需告诉 AI 您的项目构想，自动完成立项、拆解任务与排期。
                        </p>
                        <div className="flex gap-2 max-w-2xl">
                            <Input
                                placeholder="例如：帮我创建一个'Q1市场拓展计划'，目标是提升20%线索量..."
                                className="bg-background/80 border-primary/20 focus-visible:ring-primary/30"
                                value={aiPrompt}
                                onChange={(e) => setAiPrompt(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleAiCreate()}
                            />
                            <Button onClick={handleAiCreate} disabled={isAiCreating} className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/20">
                                {isAiCreating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Bot className="w-4 h-4 mr-2" />}
                                AI 立项
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Project Views */}
            {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[1, 2, 3].map(i => <div key={i} className="h-48 bg-muted/20 animate-pulse rounded-xl" />)}
                </div>
            ) : projects.length === 0 ? (
                <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed">
                    <Briefcase className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-foreground">暂无项目</h3>
                    <p className="text-muted-foreground mb-6">开始您的第一个项目吧</p>
                    <Button variant="outline" onClick={() => document.querySelector('input')?.focus()}>
                        <Plus className="w-4 h-4 mr-2" />
                        新建项目
                    </Button>
                </div>
            ) : viewMode === 'grid' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {projects.map(renderProjectCard)}
                </div>
            ) : (
                /* Kanban View */
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 min-h-[400px]">
                    {STAGE_OPTIONS.map(stage => {
                        const stageProjects = projects.filter(p => p.stage === stage.value);
                        const stageColor = {
                            planning: 'border-t-gray-400',
                            in_progress: 'border-t-blue-500',
                            completed: 'border-t-green-500',
                            on_hold: 'border-t-yellow-500',
                        }[stage.value] || 'border-t-gray-400';

                        return (
                            <div
                                key={stage.value}
                                className={cn("bg-muted/30 rounded-xl border-t-4 p-3 space-y-3", stageColor)}
                                onDragOver={(e) => e.preventDefault()}
                                onDrop={(e) => {
                                    const projectId = e.dataTransfer.getData('projectId');
                                    if (projectId) handleStageChange(projectId, stage.value);
                                }}
                            >
                                <div className="flex items-center justify-between px-1">
                                    <h4 className="text-sm font-semibold text-foreground">{stage.label}</h4>
                                    <Badge variant="outline" className="text-xs">{stageProjects.length}</Badge>
                                </div>

                                <div className="space-y-2">
                                    {stageProjects.map(project => (
                                        <div
                                            key={project.id}
                                            draggable
                                            onDragStart={(e) => e.dataTransfer.setData('projectId', project.id)}
                                            onClick={() => navigate(`/projects/${project.id}`)}
                                            className="bg-card rounded-lg p-3 border border-border hover:border-primary/50 cursor-pointer transition-all hover:shadow-md"
                                        >
                                            <h5 className="text-sm font-medium text-foreground mb-1 line-clamp-1">{project.name}</h5>
                                            <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{project.description || '暂无描述'}</p>
                                            <div className="flex items-center justify-between">
                                                <Progress value={project.progress} className="h-1.5 flex-1 mr-2" />
                                                <span className="text-xs text-muted-foreground">{project.progress}%</span>
                                            </div>
                                            {canDelete && (
                                                <div className="mt-2 flex justify-end">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="h-5 px-1 text-red-500 hover:text-red-600 text-xs"
                                                        onClick={(e) => handleDeleteProject(e, project)}
                                                    >
                                                        <Trash2 className="w-3 h-3" />
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                    ))}

                                    {stageProjects.length === 0 && (
                                        <div className="text-center py-8 text-xs text-muted-foreground border border-dashed rounded-lg">
                                            拖拽项目到此列
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            <ConfirmDialog {...ConfirmDialogProps} />
        </div>
    );
}

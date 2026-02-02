/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Bot, Plus, Briefcase, Calendar, ChevronRight, Loader2 } from "lucide-react";
import { useUser } from "@/contexts/UserContext";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import { useAuth } from "@/components/auth/AuthContext";

interface Project {
    id: string;
    name: string;
    description: string;
    status: 'planning' | 'in_progress' | 'completed' | 'on_hold';
    progress: number;
    created_at: string;
}

import { useNavigate } from "react-router-dom";

export function ProjectManagement() {
    const { user } = useUser();
    const navigate = useNavigate();
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [aiPrompt, setAiPrompt] = useState("");
    const [isAiCreating, setIsAiCreating] = useState(false);

    // ... (rest of the logic remains same until card click)

    const fetchProjects = useCallback(async () => {
        try {
            if (!user) return;
            // Use our API or Supabase directly. Let's use Supabase directly for simplicity in this component
            // matching the migration policies.
            const query = (supabase as any)
                .from('projects')
                .select('*')
                .order('created_at', { ascending: false });

            if (user.role !== 'boss') {
                query.eq('owner_id', user.id);
            }

            const { data, error } = await query;

            if (error) throw error;
            setProjects(data as any as Project[] || []);
        } catch (error) {
            console.error("Error fetching projects:", error);
            toast.error("加载项目失败");
        } finally {
            setLoading(false);
        }
    }, [user]);


    useEffect(() => {
        fetchProjects();

        // Subscribe to realtime changes
        const channel = supabase
            .channel('projects-changes')
            .on('postgres_changes', { event: '*', schema: 'public', table: 'projects' }, () => {
                fetchProjects();
            })
            .subscribe();

        return () => {
            supabase.removeChannel(channel);
        };
    }, [user, fetchProjects]); // depend on user object and fetchProjects function


    const handleAiCreate = async () => {
        if (!aiPrompt.trim()) return;
        setIsAiCreating(true);

        try {
            // Robust URL Discovery
            let url = '';
            const configuredUrl = import.meta.env.VITE_API_BASE_URL;

            if (configuredUrl) {
                url = configuredUrl.startsWith('http') ? configuredUrl : `https://${configuredUrl}`;
            } else {
                url = window.location.hostname === 'localhost' ? 'http://localhost:8000' : window.location.origin;
            }
            const endpoint = `${url.replace(/\/$/, '')}/api/chat`;

            // Get real session token
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token ? `Bearer ${token}` : `test:${user?.id}`
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

            if (!response.ok) {
                throw new Error("AI Request Failed");
            }

            // Consume the stream to ensure tool execution happens
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

            // Wait a bit for DB propagation then refresh
            setTimeout(() => {
                fetchProjects();
                toast.success("项目列表已刷新");
            }, 3000);

        } catch (error) {
            console.error(error);
            toast.error("AI 服务连接失败，请稍后重试");
        } finally {
            setIsAiCreating(false);
        }
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case 'in_progress': return <Badge variant="default" className="bg-blue-500">进行中</Badge>;
            case 'completed': return <Badge variant="default" className="bg-green-500">已完成</Badge>;
            case 'on_hold': return <Badge variant="secondary">已暂停</Badge>;
            default: return <Badge variant="outline">规划中</Badge>;
        }
    };

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-20">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">项目管理</h1>
                <p className="text-muted-foreground">全生命周期项目追踪与协作</p>
            </div>

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

            {/* Project Grid */}
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
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {projects.map((project) => (
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
                                    {getStatusBadge(project.status)}
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

                                <div className="mt-4 pt-4 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
                                    <span>负责人: {user.name}</span>
                                    <Button variant="ghost" size="sm" className="h-6 px-2 hover:text-primary">
                                        详情 <ChevronRight className="w-3 h-3 ml-1" />
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}

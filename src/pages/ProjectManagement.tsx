/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useEffect } from 'react';
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

export function ProjectManagement() {
    const { user } = useUser();
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [aiPrompt, setAiPrompt] = useState("");
    const [isAiCreating, setIsAiCreating] = useState(false);

    // Define fetchProjects as a useCallback or inside useEffect
    // To keep it simple, defining it inside useEffect is safer for dependencies
    // But we use it in subscription callback. So let's define it using useCallback or just outside.
    // Actually, we can move it inside and reference it? No.

    const fetchProjects = async () => {
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
    };

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
    }, [user]); // depend on user object


    const handleAiCreate = async () => {
        if (!aiPrompt.trim()) return;
        setIsAiCreating(true);

        try {
            // Here we simulate calling the backend AI agent
            // In a real app, we would post to /api/chat with tool_choice='create_project'
            // For now, let's implement a direct call to our new tool via an ad-hoc request 
            // OR better: use the existing chat endpoint logic.
            // But to be fast and consistent with "AI Dialog", we can just send the message to the backend chat.

            const response = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${user.id}` // Mock auth
                },
                body: JSON.stringify({
                    messages: [
                        { role: "system", content: "You are an AI assistant. User is asking to create a project within the project management context." },
                        { role: "user", content: `帮我创建一个项目，需求是：${aiPrompt}` }
                    ],
                    model: "gpt-4o-mini",
                    user_id: user.id
                })
            });

            // The stream endpoint returns SSE. For simple tool use, we might want a non-stream endpoint or handle the stream.
            // To keep it simple for this UI component, we'll assume the user uses the bottom chat bar mostly, 
            // but this input box is a "Shortcut".
            // We can just emulate a successful creation if we don't want to parse SSE here.
            // BUT, to make it real, let's parse the text response.

            // ACTUALLY, simpler approach: Just use the same supabase client to insert, 
            // but utilize LLM to parse the prompt into name/desc. 
            // Let's use the ETL metadata extraction endpoint logic? No, too complex.

            // Let's defer to the main Chat interface for "Process". 
            // But the user asked for "Conversation".
            // Let's mock the "AI Assistant" typing effect or just POST to a sync endpoint if available (not yet).

            // OK, let's just use the stream endpoint and ignore chunks, just wait for completion? No, stream never ends until closed.
            // Let's use a standard non-stream chat completion if we had one.
            // Since we don't, I will use a simple client-side parsing or just send it to the bottom chat panel.

            // BEST UX: Dispatch this prompt to the Global Chat Panel and open it!
            // I can't easily dispatch to sibling component without context.

            // Alternative: Just call the tool directly? No, that bypasses NLP.

            // Decision: Connect to /api/chat/stream, read the stream, and show a toast.
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let fullText = "";

            if (reader) {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value);
                    // Parse SSE simple logic (ignore complexity for now)
                    fullText += chunk;
                }
            }

            // If the backend tool ran, the DB is updated, and realtime will fetch it.
            // We just notify user.
            toast.success("AI 助手已收到指令处理中...");
            setAiPrompt("");

        } catch (error) {
            toast.error("AI 服务暂时不可用");
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
                        <Card key={project.id} className="group hover:shadow-lg transition-all border-border/50 hover:border-primary/50 cursor-pointer overflow-hidden relative">
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

import { useState, useEffect, useCallback } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';
import { Project, ProjectTimeline } from '@/types/nexus';
import { getApiBaseUrl } from '@/lib/apiConfig';
import { httpClient } from '@/lib/httpClient';
export type { ProjectTimeline };

export function useProjects() {
    const { profile } = useAuth();
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchProjects = useCallback(async () => {
        if (!profile?.organization_id) return;

        setLoading(true);
        const response = await httpClient.get('/api/projects');
        const data = Array.isArray(response.data?.projects) ? response.data.projects : [];
        const mapped = data.map(p => ({
            ...p,
            stage: p.status,
            type: 'Enterprise'
        }));
        setProjects(mapped as Project[]);
        setLoading(false);
    }, [profile?.organization_id]);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    return { projects, loading, refresh: fetchProjects };
}

export function useProjectDetail(projectId: string | null) {
    const [project, setProject] = useState<Project | null>(null);
    const [timeline, setTimeline] = useState<ProjectTimeline[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchDetail = useCallback(async () => {
        if (!projectId) return;
        setLoading(true);

        const [projectRes, timelineRes] = await Promise.all([
            httpClient.get(`/api/projects/${projectId}`),
            httpClient.get(`/api/projects/${projectId}/timeline`)
        ]);

        const p = projectRes.data?.project;
        if (p) {
            setProject({
                ...p,
                stage: p.status,
                type: 'Enterprise'
            });
        }

        const timelineData = timelineRes.data?.timeline || [];
        setTimeline(timelineData.map(t => ({
            ...t,
            occurred_at: t.created_at
        })));

        setLoading(false);
    }, [projectId]);

    useEffect(() => {
        fetchDetail();
    }, [fetchDetail]);

    return { project, timeline, loading, refresh: fetchDetail };
}

/** Delete a project (soft delete via backend API, boss role required) */
export function useDeleteProject() {
  return useMutation({
    mutationFn: async (projectId: string) => {
      await aiClient.fetch(`api/projects/${projectId}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      toast.success('项目已删除');
    },
    onError: (err: Error) => toast.error(err.message || '删除项目失败'),
  });
}

/* ────────────────── Team Members ────────────────── */

export interface TeamMember {
  user_id: string;
  name: string;
  avatar: string;
  department: string;
}

/** Fetch all org members for the member picker */
export function useOrgMembers() {
  const { profile } = useAuth();
  return useQuery({
    queryKey: ['org-members', profile?.organization_id],
    queryFn: async () => {
      if (!profile?.organization_id) return [];
      const response = await httpClient.get('/api/organization/members');
      const result = response.data?.members;
      return Array.isArray(result) ? result : [];
    },
    enabled: !!profile?.organization_id,
  });
}

/** Update project member_ids (stored in projects.member_ids uuid[] column) */
export function useUpdateProjectMembers() {
  return useMutation({
    mutationFn: async ({ projectId, memberIds }: { projectId: string; memberIds: string[] }) => {
      const { error } = await supabase
        .from('projects')
        .update({ member_ids: memberIds } as never)
        .eq('id', projectId);
      if (error) throw error;
    },
    onSuccess: () => toast.success('参与人员已更新'),
    onError: (err: Error) => toast.error(err.message || '更新参与人员失败'),
  });
}

/* ────────────────── Stage Transition ────────────────── */

export const STAGE_OPTIONS = [
  { value: 'planning', label: '规划中' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'on_hold', label: '已暂停' },
] as const;

/** Update project stage + auto-insert timeline milestone */
export function useUpdateProjectStage() {
  return useMutation({
    mutationFn: async ({ projectId, stage, userId }: { projectId: string; stage: string; userId: string }) => {
      const label = STAGE_OPTIONS.find(s => s.value === stage)?.label || stage;

      // Update stage via backend API
      await aiClient.fetch(`api/projects/${projectId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: stage }),
      });

      // Auto-insert timeline milestone
      await httpClient.post(`/api/projects/${projectId}/timeline`, {
        event_type: 'milestone',
        description: `项目阶段变更为「${label}」`,
      });
    },
    onSuccess: () => toast.success('阶段已更新'),
    onError: (err: Error) => toast.error(err.message || '更新阶段失败'),
  });
}

/* ────────────────── Add Timeline Event ────────────────── */

export const EVENT_TYPE_OPTIONS = [
  { value: 'milestone', label: '里程碑' },
  { value: 'meeting', label: '会议' },
  { value: 'dinner', label: '拜访/宴请' },
  { value: 'task', label: '任务' },
  { value: 'other', label: '其他' },
] as const;

export function useAddTimelineEvent() {
  return useMutation({
    mutationFn: async (event: {
      project_id: string;
      title: string;
      content: string;
      event_type: string;
      created_by: string;
    }) => {
      await httpClient.post(`/api/projects/${event.project_id}/timeline`, {
        event_type: event.event_type,
        description: `${event.title}: ${event.content}`,
      });
    },
    onSuccess: () => toast.success('进展记录已添加'),
    onError: (err: Error) => toast.error(err.message || '添加记录失败'),
  });
}

/* ────────────────── AI Analyze Progress ────────────────── */

export function useAiAnalyzeProgress() {
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const analyze = useCallback(async (project: Project, timeline: ProjectTimeline[], tasks: { title: string; status: string }[]) => {
    setAnalyzing(true);
    setResult(null);

    try {
      const context = `
项目名称: ${project.name}
项目描述: ${project.description || '无'}
当前阶段: ${project.stage}
进度: ${project.progress}%
创建时间: ${project.created_at}

时间线事件 (${timeline.length}条):
${timeline.map(t => `- [${t.event_type}] ${t.title}: ${t.content}`).join('\n')}

关联任务 (${tasks.length}条):
${tasks.map(t => `- [${t.status}] ${t.title}`).join('\n')}
`.trim();

      const endpoint = `${getApiBaseUrl()}/api/chat`;
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify({
          messages: [
            {
              role: 'system',
              content: '你是一个项目管理专家。请根据以下项目信息，给出简洁的分析报告，包括：1) 当前进展评估 2) 潜在风险 3) 建议下一步行动。用中文回答，控制在300字以内。不要使用markdown格式。'
            },
            { role: 'user', content: context }
          ],
          model: 'gpt-4o',
          agent: 'default',
        }),
      });

      if (!response.ok) throw new Error('AI 分析请求失败');

      // Read stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullText = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          // Parse SSE lines
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              try {
                const parsed = JSON.parse(data);
                const content = parsed.choices?.[0]?.delta?.content || parsed.choices?.[0]?.message?.content || '';
                fullText += content;
              } catch {
                // Not JSON, might be raw text
                if (data !== '[DONE]') fullText += data;
              }
            }
          }
          setResult(fullText);
        }
      }

      if (!fullText) setResult('AI 未返回分析结果，请稍后重试。');
    } catch (err) {
      toast.error('AI 分析失败，请稍后重试');
      setResult(null);
    } finally {
      setAnalyzing(false);
    }
  }, []);

  return { analyze, analyzing, result, clearResult: () => setResult(null) };
}

/* ────────────────── Auto Progress Calculation ────────────────── */

/** Recalculate project progress based on subtask completion ratio */
export function useRecalcProgress() {
  return useMutation({
    mutationFn: async (projectId: string) => {
      const { data: tasks } = await supabase
        .from('oa_tasks')
        .select('status')
        .eq('metadata->>project_id', projectId);

      if (!tasks || tasks.length === 0) return;

      const completed = tasks.filter(t => t.status === 'done' || t.status === 'completed').length;
      const progress = Math.round((completed / tasks.length) * 100);

      await aiClient.fetch(`api/projects/${projectId}`, {
        method: 'PATCH',
        body: JSON.stringify({ progress }),
      });
    },
  });
}

/* ────────────────── AI Predict Next Step ────────────────── */

export function useAiPredictNextStep() {
  const [predicting, setPredicting] = useState(false);
  const [prediction, setPrediction] = useState<string | null>(null);

  const predict = useCallback(async (project: Project, timeline: ProjectTimeline[]) => {
    setPredicting(true);
    setPrediction(null);

    try {
      const context = `
项目名称: ${project.name}
项目描述: ${project.description || '无'}
当前阶段: ${project.stage}
进度: ${project.progress}%

时间线事件 (${timeline.length}条，按时间倒序):
${timeline.slice(0, 10).map(t => `- [${t.event_type}] ${t.title}: ${t.content} (${new Date(t.occurred_at || t.created_at).toLocaleDateString()})`).join('\n') || '暂无事件'}
`.trim();

      const endpoint = `${getApiBaseUrl()}/api/chat`;
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify({
          messages: [
            {
              role: 'system',
              content: '你是一个项目管理专家。根据项目当前进展和历史事件，预测下一个最可能的关键节点。只输出一句话的预测建议，不超过60字，不要使用markdown格式，不要加引号。例如：建议安排与客户技术团队的需求确认会议，明确交付标准。'
            },
            { role: 'user', content: context }
          ],
          model: 'gpt-4o',
          agent: 'default',
        }),
      });

      if (!response.ok) throw new Error('AI 预测请求失败');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullText = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              try {
                const parsed = JSON.parse(data);
                const content = parsed.choices?.[0]?.delta?.content || parsed.choices?.[0]?.message?.content || '';
                fullText += content;
              } catch {
                if (data !== '[DONE]') fullText += data;
              }
            }
          }
          setPrediction(fullText);
        }
      }

      if (!fullText) setPrediction('暂无法预测，请添加更多项目进展记录。');
    } catch {
      setPrediction('AI 预测暂不可用');
    } finally {
      setPredicting(false);
    }
  }, []);

  return { predict, predicting, prediction };
}

export function useGenerateWeeklyReport() {
  return useMutation({
    mutationFn: async (projectId: string) => {
      const res = await aiClient(`/api/projects/${projectId}/weekly-report`, {
        method: 'POST',
      }) as { data?: { report: string; stats: Record<string, number> } };
      return res?.data;
    },
    onError: () => toast.error('周报生成失败'),
  });
}

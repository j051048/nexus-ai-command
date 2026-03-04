import { useState, useEffect, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';
import { Project, ProjectTimeline } from '@/types/nexus';
export type { ProjectTimeline };

export function useProjects() {
    const { profile } = useAuth();
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchProjects = useCallback(async () => {
        if (!profile?.organization_id) return;

        setLoading(true);
        const { data, error } = await supabase
            .from('projects')
            .select('*')
            // Filter by organization_id
            .eq('organization_id', profile.organization_id)
            .order('updated_at', { ascending: false });

        if (!error && data) {
            const mapped = data.map(p => ({
                ...p,
                stage: p.status, // Map status to stage for UI
                type: 'Enterprise' // Default type
            }));
            setProjects(mapped as Project[]);
        }
        setLoading(false);
        // ...
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

    useEffect(() => {
        if (!projectId) return;

        const fetchDetail = async () => {
            setLoading(true);

            const [projectRes, timelineRes] = await Promise.all([
                supabase.from('projects').select('*').eq('id', projectId).single(),
                supabase.from('project_timeline').select('*').eq('project_id', projectId).order('created_at', { ascending: false })
            ]);

            if (!projectRes.error && projectRes.data) {
                const p = projectRes.data;
                setProject({
                    ...p,
                    stage: p.status,
                    type: 'Enterprise'
                });
            }

            if (!timelineRes.error && timelineRes.data) {
                const mappedTimeline = timelineRes.data.map(t => ({
                    ...t,
                    occurred_at: t.created_at // Map created_at to occurred_at for UI
                }));
                setTimeline(mappedTimeline);
            }

            setLoading(false);
        };

        fetchDetail();
    }, [projectId]);

    return { project, timeline, loading };
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

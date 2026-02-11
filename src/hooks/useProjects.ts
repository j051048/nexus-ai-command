import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { Project, ProjectTimeline } from '@/types/nexus';
export type { ProjectTimeline };

export function useProjects() {
    const { profile } = useAuth();
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchProjects = useCallback(async () => {
        if (!profile?.organization_id) return;

        setLoading(true);
        const { data, error } = await (supabase
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            .from('projects' as any)
            .select('*')
            // Filter by organization_id
            .eq('organization_id', profile.organization_id)
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            .order('updated_at', { ascending: false }) as any);

        if (!error && data) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const mapped = (data as any[]).map(p => ({
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
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                supabase.from('projects' as any).select('*').eq('id', projectId).single() as any,
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                supabase.from('project_timeline' as any).select('*').eq('project_id', projectId).order('created_at', { ascending: false }) as any
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
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const mappedTimeline = (timelineRes.data as any[]).map(t => ({
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

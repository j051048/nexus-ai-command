import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface Project {
    id: string;
    user_id: string | null;
    name: string;
    type: string;
    stage: string;
    progress: number;
    description: string;
    created_at: string;
    updated_at: string;
}

export interface ProjectTimeline {
    id: string;
    project_id: string;
    title: string;
    content: string;
    status: string;
    event_type: string;
    occurred_at: string;
}

export function useProjects() {
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchProjects = async () => {
        setLoading(true);
        const { data, error } = await (supabase
            .from('projects' as any)
            .select('*')
            .order('updated_at', { ascending: false }) as any);

        if (!error && data) {
            setProjects(data as Project[]);
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchProjects();
    }, []);

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
                supabase.from('projects' as any).select('*').eq('id', projectId).single() as any,
                supabase.from('project_timeline' as any).select('*').eq('project_id', projectId).order('occurred_at', { ascending: false }) as any
            ]);

            if (!projectRes.error) setProject(projectRes.data as Project);
            if (!timelineRes.error) setTimeline(timelineRes.data as ProjectTimeline[]);

            setLoading(false);
        };

        fetchDetail();
    }, [projectId]);

    return { project, timeline, loading };
}

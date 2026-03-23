import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { getApiBaseUrl } from '@/lib/apiConfig';
import { useAuth } from '@/components/auth/AuthContext';

export interface SoulDocument {
  ai_name: string;
  identity: string;
  personality: string;
  values: string;
  language_style: string;
  taboos: string;
  custom_instructions: string;
  is_active: boolean;
}

export function useSoulDocument() {
  const { profile } = useAuth();
  
  return useQuery({
    queryKey: ['soul-document', profile?.organization_id],
    queryFn: async () => {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const API_BASE = getApiBaseUrl();
      const res = await fetch(`${API_BASE}/api/soul-document`, { headers });
      
      if (!res.ok) {
        // 如果端点返回404，往往是还没有配置，这是正常的，返回 null 即可
        if (res.status === 404) return null;
        throw new Error(`获取灵魂文档失败: ${res.status}`);
      }
      
      const json = await res.json();
      return (json.data as SoulDocument) || null;
    },
    staleTime: 1000 * 60 * 5, // 缓存 5 分钟
  });
}

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Plus, MessageSquare, Trash2 } from 'lucide-react';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

interface ChatSession {
  session_id: string;
  agent: string | null;
  last_activity: string;
  message_count: number;
}

interface ChatSessionListProps {
  currentSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
}

export function ChatSessionList({ currentSessionId, onSelectSession, onNewSession }: ChatSessionListProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const { session } = useAuth();

  const fetchSessions = React.useCallback(async () => {
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const token = session?.access_token;
      if (!token) return;
      
      const res = await fetch(`${baseUrl}/api/sessions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) setSessions(data.sessions || []);
    } catch (e) {
      console.error('Failed to fetch sessions:', e);
    }
  }, [session?.access_token]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const deleteSession = async (sessionId: string) => {
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const token = session?.access_token;
      await fetch(`${baseUrl}/api/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
    } catch (e) {
      console.error('Failed to delete session:', e);
    }
  };

  return (
    <div className="flex flex-col h-full border-r bg-muted/30">
      <div className="p-3 border-b">
        <Button onClick={onNewSession} className="w-full" size="sm">
          <Plus className="h-4 w-4 mr-1" /> 新建对话
        </Button>
      </div>
      <ScrollArea className="flex-1">
        {sessions.map(s => (
          <div key={s.session_id}
            className={`flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50 ${
              s.session_id === currentSessionId ? 'bg-muted' : ''
            }`}
            onClick={() => onSelectSession(s.session_id)}>
            <div className="flex items-center gap-2 min-w-0">
              <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0">
                <p className="text-sm truncate">{s.agent || '默认对话'}</p>
                <p className="text-xs text-muted-foreground">{s.message_count} 条消息</p>
              </div>
            </div>
            <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0"
              onClick={(e) => { e.stopPropagation(); deleteSession(s.session_id); }}>
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        ))}
      </ScrollArea>
    </div>
  );
}

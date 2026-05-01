import { getApiBaseUrl } from "@/lib/apiConfig";
import React, { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  History,
  Loader2,
  Calendar,
  MoreVertical,
  X
} from 'lucide-react';
import { format } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ChatSession {
  session_id: string;
  agent?: string;
  last_activity: string;
  message_count: number;
}

interface ChatHistorySidebarProps {
  currentSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
  onClose: () => void;
}

export function ChatHistorySidebar({
  currentSessionId,
  onSelectSession,
  onNewChat,
  isOpen,
  onClose
}: ChatHistorySidebarProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchSessions = async () => {
    try {
      setIsLoading(true);
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const API_BASE = getApiBaseUrl();
      const res = await fetch(`${API_BASE}/api/chat/sessions`, {
        headers: { 'Authorization': `Bearer ${session.access_token}` },
      });

      if (!res.ok) throw new Error('获取会话列表失败');
      const json = await res.json();
      // Grouping and sorting is handled by backend, but we ensure uniqueness here
      setSessions(json.data.sessions || []);
    } catch (err) {
      console.error(err);
      toast.error('无法加载历史记录');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const API_BASE = getApiBaseUrl();
      const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${session.access_token}` },
      });

      if (!res.ok) throw new Error('删除会话失败');
      
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
      if (currentSessionId === sessionId) {
        onNewChat();
      }
      toast.success('会话已删除');
    } catch (err) {
      console.error(err);
      toast.error('删除失败');
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchSessions();
    }
  }, [isOpen]);

  return (
    <div className={cn(
      "absolute top-0 right-0 h-full bg-card/98 backdrop-blur-xl border-l z-50 transition-all duration-300 ease-in-out shadow-2xl flex flex-col overflow-hidden",
      isOpen ? "w-80 opacity-100" : "w-0 opacity-0 pointer-events-none border-none"
    )}>
      <div className="p-4 border-b flex items-center justify-between bg-card-elevated/50 shrink-0">
        <div className="flex items-center gap-2 font-semibold">
          <History className="w-5 h-5 text-primary" />
          <span>对话历史</span>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 rounded-full">
          <X className="w-4 h-4" />
        </Button>
      </div>

      <div className="p-3 shrink-0">
        <Button 
          onClick={() => {
            onNewChat();
            onClose();
          }} 
          className="w-full justify-start gap-2 bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary transition-all group"
          variant="ghost"
        >
          <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform duration-300" />
          <span>开启新对话</span>
        </Button>
      </div>

      <ScrollArea className="flex-1 px-3 pb-4">
        <div className="space-y-1">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-10 text-muted-foreground gap-3">
              <Loader2 className="w-6 h-6 animate-spin text-primary/50" />
              <span className="text-xs">加载中...</span>
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-20" />
              <p className="text-xs">暂无历史记录</p>
            </div>
          ) : (
            sessions.map((session) => (
              <div
                key={session.session_id}
                onClick={() => {
                  onSelectSession(session.session_id);
                  onClose();
                }}
                className={cn(
                  "group relative p-3 rounded-xl cursor-pointer transition-all border border-transparent mb-1",
                  currentSessionId === session.session_id 
                    ? "bg-primary/10 border-primary/20 text-primary shadow-sm" 
                    : "hover:bg-secondary/80 hover:border-border/50"
                )}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0 pr-6">
                    <div className="flex items-center gap-2 mb-1">
                      <MessageSquare className={cn(
                        "w-4 h-4 shrink-0",
                        currentSessionId === session.session_id ? "text-primary" : "text-muted-foreground/60"
                      )} />
                      <span className="text-sm font-medium truncate">
                        {session.agent ? `@${session.agent}` : 'AI 助手'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-muted-foreground/70">
                      <Calendar className="w-3 h-3" />
                      <span>{format(new Date(session.last_activity), 'MM-dd HH:mm', { locale: zhCN })}</span>
                      <span className="mx-1">•</span>
                      <span>{session.message_count} 条消息</span>
                    </div>
                  </div>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity absolute top-2 right-2 rounded-lg"
                      >
                        <MoreVertical className="w-3.5 h-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-32">
                      <DropdownMenuItem 
                        onClick={(e) => handleDeleteSession(session.session_id, e)}
                        className="text-destructive focus:text-destructive flex items-center gap-2 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>删除会话</span>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
      
      <div className="p-4 border-t bg-card/50 shrink-0">
        <p className="text-[10px] text-center text-muted-foreground">
          历史记录仅保存在您的个人帐号下
        </p>
      </div>
    </div>
  );
}

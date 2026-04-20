import { useState, useRef, useEffect, useCallback } from 'react';
import { useUser } from '@/contexts/UserContext';
import { useIsMobile } from '@/hooks/use-mobile';
import { AIMessage } from '@/types/nexus';
import { toast } from 'sonner';
import { useAIStream } from '@/hooks/useAIStream';
import { useAgentTrace } from '@/hooks/useAgentTrace';
import { useOrchestrationTrace, type OrchestrationEvent } from '@/hooks/useOrchestrationTrace';
import { aiClient } from '@/api/aiClient';
import { supabase } from '@/integrations/supabase/client';
import { drainProactiveMessages, PROACTIVE_MSG_EVENT } from '@/lib/proactiveMessageStore';
import { usePageContext } from '@/hooks/usePageContext';
import { useToolMetadata } from '@/hooks/useToolMetadata';
import { useSavedPrompts } from '@/hooks/useSavedPrompts';
import { useAISettings } from '@/hooks/useAISettings';
import { handleEditMessage as treeEditMessage, handleSwitchBranch as treeSwitchBranch } from '@/lib/messageTree';

interface QuotaAlert {
  alert_level: 'normal' | 'warning' | 'critical' | 'exhausted';
  usage_percentage: number;
  alert_message: string | null;
}

interface AgentTag {
  id: string;
  name: string;
  color: string;
  description: string;
  icon: React.ReactNode;
}

export interface UseChatPanelOptions {
  isExpanded: boolean;
  onToggle: () => void;
  defaultAgent?: string;
  onSendMessage?: (message: string, response: string) => void;
  agentTags: AgentTag[];
}

export function useChatPanel({ isExpanded, onToggle, defaultAgent, onSendMessage, agentTags }: UseChatPanelOptions) {
  const { user } = useUser();
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const messagesRef = useRef<AIMessage[]>(messages);
  messagesRef.current = messages;
  const [input, setInput] = useState('');
  const [showAgents, setShowAgents] = useState(false);
  const [showQuickReplies, setShowQuickReplies] = useState(true);
  const [currentAgent, setCurrentAgent] = useState<string | undefined>(defaultAgent);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const isMobile = useIsMobile();
  const [voiceMode, setVoiceMode] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [entityDialogEntity, setEntityDialogEntity] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const autoSendRef = useRef(false);
  const inputValueRef = useRef('');
  inputValueRef.current = input;

  const {
    isTyping: isAiTyping,
    aiStatus,
    streamChat,
    stopStream,
    pendingConfirmation,
    pendingQuestion,
    circuitBreak,
    confirmAndResend,
    answerQuestion,
    dismissConfirmation,
    dismissQuestion,
    dismissCircuitBreak,
    followUpSuggestions,
    quotaInfo,
    sessionId,
    setSessionId,
  } = useAIStream({ userId: user.id });

  const { formatContextPrefix } = usePageContext();
  const { trace, startTrace, endTrace, addThinkingStep, clearTrace, addToolProgress } = useAgentTrace();
  const { orchestration, handleOrchestrationEvent, resetOrchestration } = useOrchestrationTrace();
  const [showTrace, setShowTrace] = useState(false);
  const [showToolPalette, setShowToolPalette] = useState(false);
  const { tools: toolMetadata, isLoading: toolsLoading } = useToolMetadata();
  const { savePrompt } = useSavedPrompts();
  const { data: aiSettings } = useAISettings();
  const autoExpandTrace = aiSettings?.behavior_preferences?.auto_expand_trace ?? false;
  const [quotaAlert, setQuotaAlert] = useState<QuotaAlert | null>(null);

  // Image upload state
  const imageInputRef = useRef<HTMLInputElement>(null);
  const [pendingImages, setPendingImages] = useState<Array<{ file: File; previewUrl: string; uploadedUrl?: string }>>([]);

  const handleImageUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files?.length) return;
    for (const file of Array.from(files)) {
      if (!file.type.startsWith('image/')) { toast.error('仅支持图片文件'); continue; }
      if (file.size > 10 * 1024 * 1024) { toast.error('图片大小不能超过 10MB'); continue; }
      const previewUrl = URL.createObjectURL(file);
      setPendingImages(prev => [...prev, { file, previewUrl }]);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        const token = session?.access_token;
        if (!token) { toast.error('请先登录'); continue; }
        const formData = new FormData();
        formData.append('file', file);
        const baseUrl = import.meta.env.VITE_API_BASE_URL;
        const resp = await fetch(`${baseUrl}/api/chat/upload-image`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          body: formData,
        });
        if (!resp.ok) throw new Error('上传图片失败');
        const result = await resp.json();
        const uploadedUrl = result.data?.url;
        if (uploadedUrl) {
          setPendingImages(prev => prev.map(img => img.previewUrl === previewUrl ? { ...img, uploadedUrl } : img));
        }
      } catch {
        toast.error(`图片 "${file.name}" 上传失败`);
        setPendingImages(prev => prev.filter(img => img.previewUrl !== previewUrl));
        URL.revokeObjectURL(previewUrl);
      }
    }
    if (imageInputRef.current) imageInputRef.current.value = '';
  }, []);

  const removePendingImage = useCallback((previewUrl: string) => {
    setPendingImages(prev => prev.filter(img => {
      if (img.previewUrl === previewUrl) { URL.revokeObjectURL(previewUrl); return false; }
      return true;
    }));
  }, []);

  // Quota alert fetch
  useEffect(() => {
    aiClient.fetch<{ data: QuotaAlert }>('api/usage/quota-alert')
      .then((res) => { if (res.data && res.data.alert_level !== 'normal') setQuotaAlert(res.data); })
      .catch(() => {});
  }, []);

  // Body scroll lock
  useEffect(() => {
    const shouldLock = (isExpanded && isMobile) || isFullscreen;
    if (shouldLock) {
      const originalStyle = window.getComputedStyle(document.body).overflow;
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = originalStyle; };
    }
  }, [isExpanded, isFullscreen, isMobile]);

  // ESC handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isExpanded) {
        if (isFullscreen) setIsFullscreen(false);
        else if (showTrace) setShowTrace(false);
        else if (showHistory) setShowHistory(false);
        else onToggle();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded, isFullscreen, showTrace, showHistory, onToggle]);

  // Load chat history
  const loadHistory = useCallback(async () => {
    const greeting: AIMessage = user.role === 'boss'
      ? { id: '1', role: 'assistant', content: `${user.name || '老板'}好！我是您的 AI 助理。今天有什么可以帮您的？`, timestamp: new Date() }
      : { id: '1', role: 'assistant', content: `${user.name || ''}你好！我是 Nexus AI 助手，有什么可以帮你的？`, timestamp: new Date() };

    if (!sessionId) { setMessages([greeting]); return; }
    try {
      const res = await aiClient.fetch<{ data: { messages: AIMessage[] } }>(`/api/chat/history/${sessionId}`);
      if (res?.data?.messages?.length) {
        setMessages(res.data.messages.map((m: AIMessage) => ({ ...m, timestamp: new Date(m.timestamp) })));
      } else {
        setMessages([greeting]);
      }
    } catch { setMessages([greeting]); }
  }, [sessionId, user.name, user.role]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // New chat handler
  const handleNewChat = useCallback(() => {
    setMessages([]);
    setSessionId(undefined);
    clearTrace();
    resetOrchestration();
    setShowTrace(false);
    loadHistory();
  }, [setSessionId, clearTrace, resetOrchestration, loadHistory]);

  // Send message
  const handleSend = useCallback(async () => {
    const currentInput = inputValueRef.current;
    if ((!currentInput.trim() && !pendingImages.some(img => img.uploadedUrl)) || isAiTyping) return;

    const entityMatch = currentInput.trim().match(/^\/entity\s+(.+)/);
    if (entityMatch) { setEntityDialogEntity(entityMatch[1].trim()); setInput(''); return; }

    const imageUrls = pendingImages.filter(img => img.uploadedUrl).map(img => img.uploadedUrl!);
    const userMessage: AIMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: currentInput,
      timestamp: new Date(),
      ...(imageUrls.length ? { imageUrls } : {}),
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageToSend = currentInput;
    setInput('');
    setShowQuickReplies(false);
    pendingImages.forEach(img => URL.revokeObjectURL(img.previewUrl));
    setPendingImages([]);

    let detectedAgent = currentAgent;
    for (const agent of agentTags) {
      if (messageToSend.includes(agent.name)) { detectedAgent = agent.name; break; }
    }

    try {
      startTrace();
      resetOrchestration();
      if (autoExpandTrace) setShowTrace(true);
      const contextPrefix = formatContextPrefix();
      const enrichedMessage = contextPrefix ? `${contextPrefix} ${messageToSend}` : messageToSend;
      await streamChat(enrichedMessage, messagesRef.current, detectedAgent, {
        onUpdate: (content, assistantMsgId) => {
          setMessages((prev) => {
            const exists = prev.find((m) => m.id === assistantMsgId);
            if (exists) return prev.map((m) => m.id === assistantMsgId ? { ...m, content } : m);
            return [...prev, { id: assistantMsgId, role: 'assistant', content, timestamp: new Date(), agent: detectedAgent }];
          });
        },
        onThinkingStep: (step) => addThinkingStep(step),
        onThinkingComplete: () => endTrace(),
        onToolProgress: (progress) => addToolProgress(progress.tool_name, progress.status, progress.duration_ms),
        onOrchestration: (event) => handleOrchestrationEvent(event as unknown as OrchestrationEvent),
      }, { imageUrls: imageUrls.length ? imageUrls : undefined });
      onSendMessage?.(messageToSend, messagesRef.current[messagesRef.current.length - 1]?.content || '');
      endTrace();
    } catch (e) {
      const errMsg = (e as Error)?.message || '发送失败';
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === 'assistant' && !last.content) {
          return [...prev.slice(0, -1), { ...last, content: '消息发送失败', status: 'error' as const, errorMessage: errMsg, isStreaming: false }];
        }
        return [...prev, { id: `err-${Date.now()}`, role: 'assistant' as const, content: '消息发送失败', timestamp: new Date(), status: 'error' as const, errorMessage: errMsg }];
      });
    }
  }, [isAiTyping, currentAgent, streamChat, onSendMessage, addThinkingStep, addToolProgress, endTrace, startTrace, pendingImages, autoExpandTrace, handleOrchestrationEvent, resetOrchestration, agentTags, formatContextPrefix]);

  // Command bar integration
  const commandBarSendRef = useRef(false);
  useEffect(() => {
    const handler = (e: Event) => {
      const message = (e as CustomEvent).detail?.message;
      if (message && typeof message === 'string') { setInput(message); commandBarSendRef.current = true; }
    };
    window.addEventListener('nexus:command-bar-chat', handler);
    return () => window.removeEventListener('nexus:command-bar-chat', handler);
  }, []);

  useEffect(() => {
    if (commandBarSendRef.current && input.trim()) { commandBarSendRef.current = false; handleSend(); }
  }, [input, handleSend]);

  const handleRegenerate = useCallback(() => {
    const lastUserMessage = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUserMessage) {
      setMessages((prev) => { const last = prev[prev.length - 1]; return last?.role === 'assistant' ? prev.slice(0, -1) : prev; });
      setInput(lastUserMessage.content);
    }
  }, [messages]);

  const handleRetry = useCallback(() => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    if (!lastUserMsg) return;
    setMessages((prev) => prev.filter((m) => m.status !== 'error'));
    setInput(lastUserMsg.content);
    commandBarSendRef.current = true;
  }, [messages]);

  const handleCopy = useCallback((content: string) => {
    navigator.clipboard.writeText(content).catch(() => {});
    toast.success('已复制到剪贴板');
  }, []);

  const handleExportChat = useCallback(() => {
    const msgs = messagesRef.current;
    if (!msgs.length) return;
    const exportData = msgs.map(m => ({ role: m.role, content: m.content, timestamp: m.timestamp }));
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('对话已导出');
  }, []);

  const handleShowHistory = useCallback(() => { setShowHistory(true); }, []);

  const handleDeleteMessage = useCallback((id: string) => {
    setMessages((prev) => prev.filter((m) => m.id !== id));
    toast.success('消息已删除');
  }, []);

  const handleEditMessage = useCallback((messageId: string, newContent: string) => {
    setMessages((prev) => {
      const updated = treeEditMessage(prev, messageId, newContent);
      const editedMsg = updated.find(m => m.content === newContent && m.isEdited);
      if (editedMsg) {
        const editedIdx = updated.findIndex(m => m.id === editedMsg.id);
        if (editedIdx >= 0) {
          setTimeout(() => { setInput(newContent); commandBarSendRef.current = true; }, 0);
          return updated.slice(0, editedIdx + 1);
        }
      }
      return updated;
    });
  }, []);

  const handleSwitchBranch = useCallback((parentMessageId: string, branchIndex: number) => {
    setMessages((prev) => treeSwitchBranch(prev, parentMessageId, branchIndex));
  }, []);

  const handleSelectSession = useCallback((sid: string) => {
    setSessionId(sid);
    resetOrchestration();
    clearTrace();
  }, [setSessionId, resetOrchestration, clearTrace]);

  const handleClearChat = useCallback(() => { handleNewChat(); }, [handleNewChat]);

  useEffect(() => {
    const handler = () => handleClearChat();
    window.addEventListener('nexus:command-bar-new-chat', handler);
    return () => window.removeEventListener('nexus:command-bar-new-chat', handler);
  }, [handleClearChat]);

  const insertAgent = useCallback((agent: AgentTag) => {
    setInput((prev) => prev + agent.name + ' ');
    setCurrentAgent(agent.name);
    setShowAgents(false);
    inputRef.current?.focus();
  }, []);

  const handleQuickReply = useCallback((reply: { id: string; text: string; icon?: React.ReactNode }) => {
    setInput(reply.text);
    setShowQuickReplies(false);
  }, []);

  const handleSelectTool = useCallback((tool: { name: string; description: string; domain: string | null }) => {
    const currentInput = inputValueRef.current;
    const cleaned = currentInput.endsWith('/') ? currentInput.slice(0, -1) : currentInput;
    setInput(cleaned ? `${cleaned} ${tool.description}` : tool.description);
    setShowToolPalette(false);
    inputRef.current?.focus();
  }, []);

  const handleSavePrompt = useCallback(async (prompt: string) => {
    const title = prompt.length > 20 ? prompt.slice(0, 20) + '...' : prompt;
    try {
      await savePrompt({ title, content: prompt, category: 'custom' });
      toast.success('提示词已保存');
    } catch { toast.error('保存失败'); }
  }, [savePrompt]);

  // File upload
  const handleFileUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('files', file);
    if (user?.id) formData.append('userId', user.id);
    const toastId = toast.loading('正在上传并解析文档...');
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) { toast.error('请先登录后再上传文档', { id: toastId }); return; }
      const baseUrl = import.meta.env.VITE_API_BASE_URL;
      const response = await fetch(`${baseUrl}/api/documents/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (!response.ok) throw new Error('上传文档失败');
      const result = await response.json();
      toast.success(`文档 "${file.name}" 已存入知识库 (处理了 ${result.data?.results?.[0]?.chunks_processed || result.details?.[0]?.chunks_processed || 0} 个片段)`, { id: toastId });
      setMessages((prev) => [...prev, { id: Date.now().toString(), role: 'assistant', content: `✅ 文档 "${file.name}" 已成功上传到知识库。您现在可以询问关于这份文档的问题。`, timestamp: new Date(), agent: '@知识助手' }]);
    } catch { toast.error('文档上传失败', { id: toastId }); }
    finally { if (fileInputRef.current) fileInputRef.current.value = ''; }
  }, [user?.id]);

  // Voice recording
  const toggleRecording = useCallback(async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        if (audioBlob.size < 1000) return;
        setIsTranscribing(true);
        try {
          const { data: { session } } = await supabase.auth.getSession();
          const token = session?.access_token;
          if (!token) { toast.error('请先登录'); return; }
          const formData = new FormData();
          formData.append('audio', audioBlob, 'recording.webm');
          const baseUrl = import.meta.env.VITE_API_BASE_URL;
          const resp = await fetch(`${baseUrl}/api/chat/transcribe`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
          });
          if (!resp.ok) throw new Error('转录失败');
          const result = await resp.json();
          const text = result.data?.text || result.text || '';
          if (text) {
            setInput(text);
            if (autoSendRef.current) { autoSendRef.current = false; commandBarSendRef.current = true; }
          }
        } catch { toast.error('语音转录失败'); }
        finally { setIsTranscribing(false); }
      };
      mediaRecorder.start();
      setIsRecording(true);
    } catch { toast.error('无法访问麦克风'); }
  }, [isRecording]);

  // Stop recording when panel collapses
  useEffect(() => {
    if (!isExpanded && isRecording) { mediaRecorderRef.current?.stop(); setIsRecording(false); }
  }, [isExpanded, isRecording]);


  // Load proactive messages from DB
  useEffect(() => {
    const loadProactiveFromDB = async () => {
      try {
        const lastSeenStr = localStorage.getItem(`nexus_last_seen_proactive_${user.id}`);
        let query = supabase.from('proactive_messages').select('*')
          .eq('user_id', user.id).eq('is_read', false).order('created_at', { ascending: false }).limit(10);
        if (lastSeenStr) query = query.gt('created_at', lastSeenStr);
        const { data } = await query;
        if (!data?.length) return;

        interface ProactiveRow { id: string; content: string; created_at: string; metadata?: { source?: string; task_id?: string; task_name?: string } }

        // Filter out orphan scheduled tasks
        const taskIds = data.filter((r: ProactiveRow) => r.metadata?.source === 'scheduled_task' && r.metadata?.task_id).map((r: ProactiveRow) => r.metadata!.task_id as string);
        const taskNames = data.filter((r: ProactiveRow) => r.metadata?.source === 'scheduled_task' && !r.metadata?.task_id && r.metadata?.task_name).map((r: ProactiveRow) => r.metadata!.task_name as string);
        let deletedTaskIds = new Set<string>();
        let orphanTaskNames = new Set<string>();
        try {
          if (taskIds.length) {
            const { data: existing } = await supabase.from('user_scheduled_tasks').select('id').in('id', taskIds);
            const existingSet = new Set((existing || []).map((t: { id: string }) => t.id));
            deletedTaskIds = new Set(taskIds.filter(id => !existingSet.has(id)));
          }
          if (taskNames.length) {
            const { data: existingByName } = await supabase.from('user_scheduled_tasks').select('name').in('name', taskNames);
            const existingNames = new Set((existingByName || []).map((t: { name: string }) => t.name));
            orphanTaskNames = new Set(taskNames.filter(n => !existingNames.has(n)));
          }
        } catch {}

        const validData = (deletedTaskIds.size > 0 || orphanTaskNames.size > 0)
          ? data.filter((r: ProactiveRow) => {
              if (r.metadata?.source !== 'scheduled_task') return true;
              if (r.metadata?.task_id && deletedTaskIds.has(r.metadata.task_id as string)) return false;
              if (!r.metadata?.task_id && r.metadata?.task_name && orphanTaskNames.has(r.metadata.task_name as string)) return false;
              return true;
            })
          : data;
        if (!validData.length) return;

        const maxTime = Math.max(...validData.map((r: ProactiveRow) => new Date(r.created_at).getTime()));
        localStorage.setItem(`nexus_last_seen_proactive_${user.id}`, new Date(maxTime).toISOString());

        const seen = new Set<string>();
        const deduplicated = validData.filter((row: ProactiveRow) => {
          const contentKey = `${row.metadata?.task_name || ''}::${row.content?.slice(0, 100) || ''}`;
          if (seen.has(contentKey)) return false;
          seen.add(contentKey);
          return true;
        });

        setMessages(prev => {
          const existingIds = new Set(prev.map(m => m.id));
          const existingContents = new Set(prev.filter(m => m.isProactive).map(m => m.content?.slice(0, 100)));
          const newMsgs = deduplicated
            .filter((row: ProactiveRow) => !existingIds.has(`db-proactive-${row.id}`) && !existingContents.has(row.content?.slice(0, 100) || ''))
            .map((row: ProactiveRow) => ({
              id: `db-proactive-${row.id}`, role: 'assistant' as const, content: row.content || '',
              timestamp: new Date(row.created_at),
              agent: row.metadata?.task_name ? `${row.metadata?.source === 'smart_reminder' ? '智能提醒' : '定时任务'}: ${row.metadata.task_name}` : '主动推送',
              isProactive: true,
            }));
          return newMsgs.length > 0 ? [...prev, ...newMsgs] : prev;
        });
      } catch {}
    };
    loadProactiveFromDB();
  }, [user.id]);

  // Proactive messages
  useEffect(() => {
    const injectProactive = () => {
      const pending = drainProactiveMessages();
      if (!pending.length) return;
      const maxTime = Math.max(...pending.map(p => p.receivedAt.getTime()));
      const lastSeenStr = localStorage.getItem(`nexus_last_seen_proactive_${user.id}`);
      if (!lastSeenStr || maxTime > new Date(lastSeenStr).getTime()) {
        localStorage.setItem(`nexus_last_seen_proactive_${user.id}`, new Date(maxTime).toISOString());
      }
      setMessages(prev => {
        const existingIds = new Set(prev.map(m => m.id));
        const newMsgs = pending
          .filter(pm => !existingIds.has(`proactive-${pm.sessionId}`))
          .map(pm => ({ id: `proactive-${pm.sessionId}`, role: 'assistant' as const, content: pm.message, timestamp: pm.receivedAt, agent: `${pm.title}`, isProactive: true }));
        return newMsgs.length > 0 ? [...prev, ...newMsgs] : prev;
      });
    };
    injectProactive();
    window.addEventListener(PROACTIVE_MSG_EVENT, injectProactive);
    return () => window.removeEventListener(PROACTIVE_MSG_EVENT, injectProactive);
  }, [user.id]);

  // Scroll follows streaming content
  const lastMsgContent = messages[messages.length - 1]?.content;
  const scrollTrigger = `${messages.length}::${typeof lastMsgContent === 'string' ? lastMsgContent.length : 0}`;
  const scrollRafRef = useRef<number>(0);

  useEffect(() => {
    if (scrollRafRef.current) cancelAnimationFrame(scrollRafRef.current);
    scrollRafRef.current = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: isAiTyping ? 'instant' : 'smooth' });
      scrollRafRef.current = 0;
    });
    return () => { if (scrollRafRef.current) cancelAnimationFrame(scrollRafRef.current); };
  }, [scrollTrigger, isAiTyping]);

  // Focus input when expanded
  useEffect(() => {
    if (isExpanded && inputRef.current) setTimeout(() => inputRef.current?.focus(), 100);
  }, [isExpanded]);

  // Global ESC to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isExpanded) {
        if (isFullscreen) setIsFullscreen(false);
        else if (showTrace) setShowTrace(false);
        else if (showHistory) setShowHistory(false);
        else onToggle();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded, isFullscreen, showTrace, showHistory, onToggle]);

  // Cleanup media recorder on unmount
  useEffect(() => {
    return () => { if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') mediaRecorderRef.current.stop(); };
  }, []);

  return {
    // State
    user, messages, setMessages, input, setInput, showAgents, setShowAgents, showQuickReplies,
    currentAgent, setCurrentAgent, isFullscreen, setIsFullscreen, isRecording, isMobile,
    voiceMode, setVoiceMode, showMobileMenu, setShowMobileMenu, isTranscribing,
    showHistory, setShowHistory, entityDialogEntity, setEntityDialogEntity,
    isAiTyping, aiStatus, showTrace, setShowTrace, showToolPalette, setShowToolPalette,
    quotaAlert, setQuotaAlert, pendingImages,
    // Refs
    messagesEndRef, inputRef, fileInputRef, imageInputRef,
    // Stream state
    stopStream, pendingConfirmation, pendingQuestion, circuitBreak,
    confirmAndResend, answerQuestion, dismissConfirmation, dismissQuestion, dismissCircuitBreak,
    followUpSuggestions, quotaInfo, sessionId,
    // Trace
    trace, orchestration,
    // Tools
    toolMetadata, toolsLoading,
    // Handlers
    handleSend, handleRegenerate, handleRetry, handleCopy, handleExportChat,
    handleShowHistory, handleDeleteMessage, handleEditMessage, handleSwitchBranch,
    handleClearChat, handleNewChat, handleSelectSession, insertAgent, handleQuickReply, handleSelectTool,
    handleSavePrompt, handleFileUpload, handleImageUpload, removePendingImage,
    toggleRecording,
  };
}

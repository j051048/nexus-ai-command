import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { useUser } from '@/contexts/UserContext';
import {
  Zap,
  ThumbsUp,
  Lightbulb,
  Sparkles,
} from 'lucide-react';
import { AIMessage } from '@/types/nexus';
import { toast } from 'sonner';
import { useAIStream } from '@/hooks/useAIStream';
import { useAgentTrace } from '@/hooks/useAgentTrace';
import { aiClient } from '@/api/aiClient';
import { supabase } from '@/integrations/supabase/client';
import { drainProactiveMessages, PROACTIVE_MSG_EVENT } from '@/lib/proactiveMessageStore';
import { ChatHeader } from './ChatHeader';
import { ChatMessageList } from './ChatMessageList';
import { ChatInputArea } from './ChatInputArea';
import { ChatSuggestions } from './ChatSuggestions';

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

interface EnhancedAIChatPanelProps {
  isExpanded: boolean;
  onToggle: () => void;
  defaultAgent?: string;
  onSendMessage?: (message: string, response: string) => void;
  variant?: 'overlay' | 'embedded';
  compact?: boolean;
}

const agentTags: AgentTag[] = [
  {
    id: 'sales',
    name: '@销售指挥官',
    color: 'text-blue-500 bg-blue-500/10',
    description: '销售策略、商机分析、客户洞察',
    icon: <Zap className="w-3 h-3" />,
  },
  {
    id: 'performance',
    name: '@绩效教练',
    color: 'text-green-500 bg-green-500/10',
    description: '目标追踪、绩效分析、激励建议',
    icon: <ThumbsUp className="w-3 h-3" />,
  },
  {
    id: 'approval',
    name: '@企业小助手',
    color: 'text-orange-500 bg-orange-500/10',
    description: '审批流程、报销查询、政策咨询',
    icon: <Lightbulb className="w-3 h-3" />,
  },
  {
    id: 'knowledge',
    name: '@知识助手',
    color: 'text-purple-500 bg-purple-500/10',
    description: '文档检索、知识问答、资料查找',
    icon: <Sparkles className="w-3 h-3" />,
  },
];

export function EnhancedAIChatPanel({
  isExpanded,
  onToggle,
  defaultAgent,
  onSendMessage,
  variant = 'overlay',
  compact = false,
}: EnhancedAIChatPanelProps) {
  const { user } = useUser();
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [input, setInput] = useState('');
  const [showAgents, setShowAgents] = useState(false);
  const [showQuickReplies, setShowQuickReplies] = useState(true);
  const [currentAgent, setCurrentAgent] = useState<string | undefined>(defaultAgent);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [voiceMode, setVoiceMode] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const autoSendRef = useRef(false);
  const inputValueRef = useRef('');

  // Keep ref in sync with state so handleSend reads latest value without re-creating
  inputValueRef.current = input;

  const { isTyping: isAiTyping, aiStatus, streamChat, stopStream, pendingConfirmation, pendingQuestion, confirmAndResend, answerQuestion, dismissConfirmation, dismissQuestion } = useAIStream({ userId: user.id });

  const { trace, startTrace, endTrace, addThinkingStep, clearTrace } = useAgentTrace();
  const [showTrace, setShowTrace] = useState(false);

  const [quotaAlert, setQuotaAlert] = useState<QuotaAlert | null>(null);

  useEffect(() => {
    aiClient.fetch<{ data: QuotaAlert }>('api/usage/quota-alert')
      .then((res) => {
        if (res.data && res.data.alert_level !== 'normal') {
          setQuotaAlert(res.data);
        }
      })
      .catch(() => { /* silent — non-critical */ });
  }, []);

  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  useEffect(() => {
    const greeting: AIMessage = user.role === 'boss'
      ? {
          id: '1',
          role: 'assistant',
          content: `早上好，${user.name}！📊\n\n我是您的AI助手，随时为您服务。\n您可以问我：\n• 有哪些待审批事项？\n• 本周销售情况如何？\n• 查看经营数据报表\n\n有什么需要了解的？`,
          timestamp: new Date(),
          agent: '@企业小助手',
        }
      : {
          id: '1',
          role: 'assistant',
          content: `早上好，${user.name}！我是您的AI助手 🚀\n\n您可以问我：\n• 今天有什么待办事项？\n• 帮我查看商机进展\n• 我的绩效数据\n\n有什么我可以帮您的？`,
          timestamp: new Date(),
          agent: '@销售指挥官',
        };
    setMessages([greeting]);
  }, [user.role, user.name]);

  // 注入 AI 主动推送消息（定时任务结果、事件告警等）
  useEffect(() => {
    const injectProactive = () => {
      const pending = drainProactiveMessages();
      if (pending.length === 0) return;
      setMessages(prev => {
        const existingIds = new Set(prev.map(m => m.id));
        const newMsgs = pending
          .filter(pm => !existingIds.has(`proactive-${pm.sessionId}`))
          .map(pm => ({
            id: `proactive-${pm.sessionId}`,
            role: 'assistant' as const,
            content: pm.message,
            timestamp: pm.receivedAt,
            agent: `${pm.title}`,
            isProactive: true,
          }));
        return newMsgs.length > 0 ? [...prev, ...newMsgs] : prev;
      });
    };

    // Drain on mount (handles mobile panel opening after WS message arrived)
    injectProactive();

    window.addEventListener(PROACTIVE_MSG_EVENT, injectProactive);
    return () => window.removeEventListener(PROACTIVE_MSG_EVENT, injectProactive);
  }, []);

  // 从 DB 拉取离线期间的主动消息（WS 断开时的兜底）
  // 按 task_name 去重，同类提醒只显示最新一条，避免重复刷屏
  useEffect(() => {
    const loadProactiveFromDB = async () => {
      try {
        const { data, error } = await supabase
          .from('chat_messages')
          .select('id, session_id, role, content, metadata, created_at')
          .eq('user_id', user.id)
          .eq('role', 'assistant')
          .filter('metadata->>source', 'in', '("scheduled_task","smart_reminder")')
          .gte('created_at', new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString())
          .order('created_at', { ascending: false })
          .limit(20);

        if (error || !data?.length) return;

        // Deduplicate by task_name + content: keep only the latest per unique combination
        const seen = new Set<string>();
        const deduplicated = data.filter((row: any) => {
          const taskName = row.metadata?.task_name || '';
          const contentKey = `${taskName}::${row.content?.slice(0, 100) || ''}`;
          if (seen.has(contentKey)) return false;
          seen.add(contentKey);
          return true;
        });

        setMessages(prev => {
          const existingIds = new Set(prev.map(m => m.id));
          // Also check for duplicate content already in chat
          const existingContents = new Set(
            prev.filter(m => (m as any).isProactive).map(m => m.content?.slice(0, 100))
          );
          const newMsgs = deduplicated
            .filter((row: any) =>
              !existingIds.has(`db-proactive-${row.id}`) &&
              !existingContents.has(row.content?.slice(0, 100))
            )
            .map((row: any) => ({
              id: `db-proactive-${row.id}`,
              role: 'assistant' as const,
              content: row.content,
              timestamp: new Date(row.created_at),
              agent: row.metadata?.task_name
                ? `${row.metadata?.source === 'smart_reminder' ? '智能提醒' : '定时任务'}: ${row.metadata.task_name}`
                : '主动推送',
              isProactive: true,
            }));
          return newMsgs.length > 0 ? [...prev, ...newMsgs] : prev;
        });
      } catch {
        // silent — 非关键路径
      }
    };

    loadProactiveFromDB();
  }, [user.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  useEffect(() => {
    if (isExpanded && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isExpanded]);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  useEffect(() => {
    if (!isExpanded && mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isExpanded]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('files', file);
    if (user?.id) {
      formData.append('userId', user.id);
    }

    const toastId = toast.loading('正在上传并解析文档...');

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) {
        toast.error('请先登录后再上传文档', { id: toastId });
        return;
      }

      const baseUrl = import.meta.env.VITE_API_BASE_URL;
      const response = await fetch(`${baseUrl}/api/documents/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) throw new Error('Upload failed');

      const result = await response.json();
      toast.success(
        `文档 "${file.name}" 已存入知识库 (处理了 ${result.data?.results?.[0]?.chunks_processed || result.details?.[0]?.chunks_processed || 0} 个片段)`,
        { id: toastId }
      );

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: 'assistant',
          content: `✅ 文档 "${file.name}" 已成功上传到知识库。您现在可以询问关于这份文档的问题。`,
          timestamp: new Date(),
          agent: '@知识助手',
        },
      ]);
    } catch (error) {
      toast.error('文档上传失败', { id: toastId });
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSend = useCallback(async () => {
    const currentInput = inputValueRef.current;
    if (!currentInput.trim() || isAiTyping) return;

    const userMessage: AIMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: currentInput,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageToSend = currentInput;
    setInput('');
    setShowQuickReplies(false);

    let detectedAgent = currentAgent;
    for (const agent of agentTags) {
      if (messageToSend.includes(agent.name)) {
        detectedAgent = agent.name;
        break;
      }
    }

    try {
      startTrace();
      await streamChat(
        messageToSend,
        messages,
        detectedAgent,
        {
          onUpdate: (content, assistantMsgId) => {
            setMessages((prev) => {
              const exists = prev.find((m) => m.id === assistantMsgId);
              if (exists) {
                return prev.map((m) =>
                  m.id === assistantMsgId ? { ...m, content } : m
                );
              } else {
                return [
                  ...prev,
                  {
                    id: assistantMsgId,
                    role: 'assistant',
                    content,
                    timestamp: new Date(),
                    agent: detectedAgent,
                  },
                ];
              }
            });
          },
          onThinkingStep: (step) => {
            addThinkingStep(step);
          },
          onThinkingComplete: () => {
            endTrace();
          },
        }
      );

      onSendMessage?.(messageToSend, messages[messages.length - 1]?.content || '');
      endTrace();
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.content !== ''));
    }
  }, [isAiTyping, currentAgent, messages, streamChat, onSendMessage, addThinkingStep, endTrace, startTrace]);

  const commandBarSendRef = useRef(false);
  useEffect(() => {
    const handler = (e: Event) => {
      const message = (e as CustomEvent).detail?.message;
      if (message && typeof message === 'string') {
        setInput(message);
        commandBarSendRef.current = true;
      }
    };
    window.addEventListener('nexus:command-bar-chat', handler);
    return () => window.removeEventListener('nexus:command-bar-chat', handler);
  }, []);

  useEffect(() => {
    if (commandBarSendRef.current && input.trim()) {
      commandBarSendRef.current = false;
      handleSend();
    }
  }, [input, handleSend]);

  const handleRegenerate = useCallback(() => {
    const lastUserMessage = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUserMessage) {
      setMessages((prev) => prev.slice(0, -1));
      setInput(lastUserMessage.content);
    }
  }, [messages]);

  const handleCopy = useCallback((content: string) => {
    navigator.clipboard.writeText(content);
    toast.success('已复制到剪贴板');
  }, []);

  const handleDeleteMessage = useCallback((id: string) => {
    setMessages((prev) => prev.filter((m) => m.id !== id));
    toast.success('消息已删除');
  }, []);

  const handleClearChat = useCallback(() => {
    setMessages([]);
    setShowQuickReplies(true);
    toast.success('对话已清空');
  }, []);

  // Listen for "new chat" command from Ctrl+K command bar
  useEffect(() => {
    const handler = () => handleClearChat();
    window.addEventListener('nexus:command-bar-new-chat', handler);
    return () => window.removeEventListener('nexus:command-bar-new-chat', handler);
  }, [handleClearChat]);

  const insertAgent = (agent: AgentTag) => {
    setInput((prev) => prev + agent.name + ' ');
    setCurrentAgent(agent.name);
    setShowAgents(false);
    inputRef.current?.focus();
  };

  const handleQuickReply = (reply: { id: string; text: string; icon?: React.ReactNode }) => {
    setInput(reply.text);
    setShowQuickReplies(false);
  };

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/mp4')
          ? 'audio/mp4'
          : 'audio/webm';

      const recorder = new MediaRecorder(stream, { mimeType });
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        if (audioBlob.size < 1000) {
          toast.info('录音时间太短，请再试一次');
          return;
        }
        setIsTranscribing(true);
        try {
          const result = await aiClient.uploadAudio(audioBlob, mimeType);
          if (result.data?.text) {
            setInput(result.data.text);
            autoSendRef.current = true;
          } else {
            toast.info('未识别到语音，请重试');
          }
        } catch (err) {
          console.error('[Voice] STT failed:', err);
          const errMsg = (err as Error)?.message || '';
          if (errMsg.includes('繁忙') || errMsg.includes('429') || errMsg.includes('稍后')) {
            toast.error('语音服务繁忙，请等几秒后再试');
          } else if (errMsg.includes('API Key') || errMsg.includes('401')) {
            toast.error('AI API Key 未配置或无效');
          } else {
            toast.error('语音识别失败，请重试');
          }
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start(100);
      setIsRecording(true);
      if (navigator.vibrate) navigator.vibrate(50);
    } catch (err) {
      if ((err as Error).name === 'NotAllowedError') {
        toast.error('请允许麦克风权限后重试');
      } else {
        console.error('[Voice] getUserMedia failed:', err);
        toast.error('无法访问麦克风');
      }
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (navigator.vibrate) navigator.vibrate(50);
    }
  }, []);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, stopRecording, startRecording]);

  useEffect(() => {
    if (autoSendRef.current && input.trim()) {
      autoSendRef.current = false;
      handleSend();
    }
  }, [input, handleSend]);

  const panelHeightClass = useMemo(() => {
    if (isFullscreen) return 'h-[100dvh]';
    if (isExpanded) return 'h-[85dvh] md:h-[500px]';
    return 'h-16';
  }, [isExpanded, isFullscreen]);

  return (
    <>
      {isMobile && isExpanded && variant !== 'embedded' && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 animate-fade-in"
          onClick={onToggle}
        />
      )}

      <div
        className={cn(
          'bg-card border-border transition-all duration-300 shadow-xl flex flex-col',
          isMobile && isExpanded && variant !== 'embedded' ? 'fixed inset-0 z-50 bg-background' : '',
          isMobile && variant === 'embedded' ? 'relative h-full w-full bg-background' : '',
          !isMobile && variant === 'overlay' ? 'fixed z-50 shadow-[0_-4px_20px_-1px_rgba(0,0,0,0.1)]' : '',
          !isMobile && variant === 'embedded' ? 'relative h-full w-full border-r' : '',
          !isMobile && variant === 'overlay' && isFullscreen ? 'inset-0 rounded-none' : '',
          !isMobile && variant === 'overlay' && !isFullscreen ? 'bottom-0 left-0 right-0 md:left-64 md:right-80 rounded-t-2xl md:rounded-none' : '',
          variant === 'overlay' && !isMobile ? panelHeightClass : 'h-full'
        )}
      >
        {!compact && (
          <ChatHeader
            isExpanded={isExpanded}
            onToggle={onToggle}
            variant={variant}
            isAiTyping={isAiTyping}
            aiStatus={aiStatus}
            isFullscreen={isFullscreen}
            setIsFullscreen={setIsFullscreen}
            isMobile={isMobile}
            showTrace={showTrace}
            setShowTrace={setShowTrace}
            handleClearChat={handleClearChat}
          />
        )}

        {(isExpanded || variant === 'embedded') && (
          <div className={cn(
            'flex flex-col flex-1 min-h-0',
            variant === 'overlay' && isFullscreen ? 'h-[calc(100dvh-4rem)]' : '',
            variant === 'overlay' && !isFullscreen ? 'h-[calc(85dvh-4rem)] md:h-[436px]' : ''
          )}>
            <ChatMessageList
              messages={messages}
              setMessages={setMessages}
              isAiTyping={isAiTyping}
              aiStatus={aiStatus}
              userId={user.id}
              handleCopy={handleCopy}
              handleRegenerate={handleRegenerate}
              handleDeleteMessage={handleDeleteMessage}
              pendingConfirmation={pendingConfirmation}
              confirmAndResend={confirmAndResend}
              dismissConfirmation={dismissConfirmation}
              pendingQuestion={pendingQuestion}
              answerQuestion={answerQuestion}
              dismissQuestion={dismissQuestion}
              showTrace={showTrace}
              setShowTrace={setShowTrace}
              trace={trace}
              messagesEndRef={messagesEndRef}
            />

            <ChatSuggestions
              showQuickReplies={showQuickReplies}
              messagesCount={messages.length}
              onQuickReply={handleQuickReply}
            />

            <ChatInputArea
              input={input}
              setInput={setInput}
              handleSend={handleSend}
              isAiTyping={isAiTyping}
              stopStream={stopStream}
              currentAgent={currentAgent}
              setCurrentAgent={setCurrentAgent}
              showAgents={showAgents}
              setShowAgents={setShowAgents}
              agentTags={agentTags}
              insertAgent={insertAgent}
              isMobile={isMobile}
              voiceMode={voiceMode}
              setVoiceMode={setVoiceMode}
              isRecording={isRecording}
              isTranscribing={isTranscribing}
              toggleRecording={toggleRecording}
              showMobileMenu={showMobileMenu}
              setShowMobileMenu={setShowMobileMenu}
              inputRef={inputRef}
              fileInputRef={fileInputRef}
              handleFileUpload={handleFileUpload}
              variant={variant}
              quotaAlert={quotaAlert}
              setQuotaAlert={setQuotaAlert}
            />
          </div>
        )}
      </div>
    </>
  );
}

export default EnhancedAIChatPanel;

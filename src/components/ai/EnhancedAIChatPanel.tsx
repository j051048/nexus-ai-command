/**
 * P1 UX Enhancement: Enhanced AI Chat Panel
 * 增强版 AI 聊天面板，支持更多交互功能
 */

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { useUser } from '@/contexts/UserContext';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Bot,
  ChevronUp,
  ChevronDown,
  Send,
  Mic,
  MicOff,
  Sparkles,
  AtSign,
  Loader2,
  Paperclip,
  Plus,
  Copy,
  Check,
  RotateCcw,
  ThumbsUp,
  ThumbsDown,
  MoreHorizontal,
  Trash2,
  Download,
  Maximize2,
  Minimize2,
  X,
  Lightbulb,
  History,
  Keyboard,
  Settings,
  Zap,
  AlertTriangle,
} from 'lucide-react';
import { AIMessage } from '@/types/nexus';
import { toast } from 'sonner';
import { useAIStream } from '@/hooks/useAIStream';
import { aiClient } from '@/api/aiClient';
import { PulseDot } from '@/components/common/AnimatedComponents';
import { MessageBubble } from './MessageBubble';
import { supabase } from '@/integrations/supabase/client';


// ==================== 类型定义 ====================

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

interface QuickReply {
  id: string;
  text: string;
  icon?: React.ReactNode;
}

interface EnhancedAIChatPanelProps {
  isExpanded: boolean;
  onToggle: () => void;
  defaultAgent?: string;
  onSendMessage?: (message: string, response: string) => void;
  variant?: 'overlay' | 'embedded'; // New prop
}

// ==================== 常量配置 ====================

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

const defaultQuickReplies: QuickReply[] = [
  { id: '1', text: '查看今日待办', icon: <History className="w-3 h-3" /> },
  { id: '2', text: '本周销售汇总', icon: <Zap className="w-3 h-3" /> },
  { id: '3', text: '分析商机进度', icon: <Lightbulb className="w-3 h-3" /> },
  { id: '4', text: '帮助指南', icon: <Keyboard className="w-3 h-3" /> },
];

// ==================== 子组件 ====================

// 移除内部定义的 MessageBubble 组件和接口


// ==================== 主组件 ====================

export function EnhancedAIChatPanel({
  isExpanded,
  onToggle,
  defaultAgent,
  onSendMessage,
  variant = 'overlay', // Default to overlay
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

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const { isTyping: isAiTyping, aiStatus, streamChat } = useAIStream({ userId: user.id });

  // Quota alert state
  const [quotaAlert, setQuotaAlert] = useState<QuotaAlert | null>(null);

  // Fetch quota alert on mount
  useEffect(() => {
    aiClient.fetch<{ data: QuotaAlert }>('api/usage/quota-alert')
      .then((res) => {
        if (res.data && res.data.alert_level !== 'normal') {
          setQuotaAlert(res.data);
        }
      })
      .catch(() => { /* silent — non-critical */ });
  }, []);

  // A5: 移动端检测
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  // 初始化欢迎消息
  useEffect(() => {
    const greeting: AIMessage = user.role === 'boss'
      ? {
          id: '1',
          role: 'assistant',
          content: `早上好，${user.name}！📊\n\n今日AI摘要：\n• 3条异常审批待您确认（均已超时预警）\n• 本周销售激励已自动发放 ¥12,800\n• 团队整体赢率提升 8.5%\n\n无需其他操作，一切尽在掌控。有什么需要了解的？`,
          timestamp: new Date(),
          agent: '@企业小助手',
        }
      : {
          id: '1',
          role: 'assistant',
          content: `早上好，${user.name}！我是您的AI指挥官 🚀\n\n今日重点：\n• 张教授商机进入关键阶段，建议上午跟进\n• 您的绩效分已达87分，距离"销售精英"徽章仅差13分\n• 有1条新线索待查看\n\n有什么我可以帮您的？`,
          timestamp: new Date(),
          agent: '@销售指挥官',
        };
    setMessages([greeting]);
  }, [user.role, user.name]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isExpanded && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isExpanded]);

  // Cleanup speech recognition on unmount or panel collapse
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
        recognitionRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!isExpanded && recognitionRef.current) {
      recognitionRef.current.abort();
      recognitionRef.current = null;
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
      // P0 Security Fix: Get auth token for file upload
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) {
        toast.error('请先登录后再上传文档', { id: toastId });
        return;
      }

      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';
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
      console.error(error);
      toast.error('文档上传失败', { id: toastId });
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSend = useCallback(async () => {
    if (!input.trim() || isAiTyping) return;

    const userMessage: AIMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageToSend = input;
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
      await streamChat(
        messageToSend,
        messages,
        detectedAgent,
        (content, assistantMsgId) => {
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
        }
      );

      onSendMessage?.(messageToSend, messages[messages.length - 1]?.content || '');
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.content !== ''));
    }
  }, [input, isAiTyping, currentAgent, messages, streamChat, onSendMessage]);

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

  const insertAgent = (agent: AgentTag) => {
    setInput((prev) => prev + agent.name + ' ');
    setCurrentAgent(agent.name);
    setShowAgents(false);
    inputRef.current?.focus();
  };

  const handleQuickReply = (reply: QuickReply) => {
    setInput(reply.text);
    setShowQuickReplies(false);
  };

  const toggleRecording = useCallback(() => {
    // If already recording, stop
    if (isRecording && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsRecording(false);
      return;
    }

    // Check browser support
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      toast.warning('您的浏览器不支持语音输入，请使用 Chrome 浏览器');
      return;
    }

    // Create and configure recognition instance
    const recognition = new SpeechRecognitionAPI();
    recognition.lang = 'zh-CN';
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsRecording(true);
      toast.info('正在聆听，请说话...');
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      // Append final transcript to input, or show interim results
      if (finalTranscript) {
        setInput((prev) => prev + finalTranscript);
      } else if (interimTranscript) {
        // For interim results, we show them as a preview
        // We store the base input before speech started and append interim
        setInput((prev) => {
          // Remove any previous interim content by finding the base
          const base = prev.replace(/\u200B.*$/, '');
          return base + interimTranscript;
        });
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      setIsRecording(false);
      recognitionRef.current = null;

      switch (event.error) {
        case 'no-speech':
          toast.info('未检测到语音，请重试');
          break;
        case 'audio-capture':
          toast.error('无法访问麦克风，请检查权限设置');
          break;
        case 'not-allowed':
          toast.error('麦克风权限被拒绝，请在浏览器设置中允许访问');
          break;
        case 'network':
          toast.error('网络错误，语音识别需要网络连接');
          break;
        default:
          toast.error(`语音识别错误: ${event.error}`);
      }
    };

    recognition.onend = () => {
      setIsRecording(false);
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
    } catch (err) {
      toast.error('启动语音识别失败，请重试');
      setIsRecording(false);
      recognitionRef.current = null;
    }
  }, [isRecording]);

  const panelHeightClass = useMemo(() => {
    if (isFullscreen) return 'h-[100dvh]';
    if (isExpanded) return 'h-[85dvh] md:h-[500px]';
    return 'h-16';
  }, [isExpanded, isFullscreen]);

  return (
    <>
      {/* A5: 移动端背景遮罩（仅移动端全屏时显示） */}
      {isMobile && isExpanded && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 animate-fade-in"
          onClick={onToggle}
        />
      )}

      <div
        className={cn(
          'bg-card border-border transition-all duration-300 shadow-xl flex flex-col',
          // A5: 移动端全屏样式
          isMobile && isExpanded ? 'fixed inset-0 z-50 bg-background' : '',
          // 桌面端或移动端未展开时的样式
          !isMobile && variant === 'overlay' ? 'fixed z-50 shadow-[0_-4px_20px_-1px_rgba(0,0,0,0.1)]' : '',
          !isMobile && variant === 'embedded' ? 'relative h-full w-full border-r' : '',
          !isMobile && variant === 'overlay' && isFullscreen ? 'inset-0 rounded-none' : '',
          !isMobile && variant === 'overlay' && !isFullscreen ? 'bottom-0 left-0 right-0 md:left-64 md:right-80 rounded-t-2xl md:rounded-none' : '',
          variant === 'overlay' && !isMobile ? panelHeightClass : 'h-full'
        )}
      >
        {/* Header */}
        <div
          className={cn(
            'h-16 px-4 md:px-6 flex items-center justify-between cursor-pointer hover:bg-card-elevated/50 transition-colors',
            isFullscreen || isMobile ? 'rounded-none' : 'rounded-t-2xl md:rounded-t-none'
          )}
          onClick={(!isFullscreen && !isMobile) ? onToggle : undefined}
        >
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-lg">
                <Bot className="w-5 h-5 text-primary-foreground" />
              </div>
              {isAiTyping && (
                <span className="absolute -bottom-0.5 -right-0.5">
                  <PulseDot color="success" size="sm" />
                </span>
              )}
            </div>
            <div>
              <h3 className="font-semibold text-foreground flex items-center gap-2">
                AI 指挥中心
                <Sparkles className="w-4 h-4 text-primary" />
              </h3>
              <div className="text-xs text-muted-foreground flex items-center gap-2">
                  <div className="flex items-center gap-2">
                    {/* Visual Thinking Process */}
                    {aiStatus ? (
                      <div className="flex items-center gap-1.5 bg-secondary/80 px-2 py-0.5 rounded-full animate-pulse">
                         <Loader2 className="w-3 h-3 animate-spin text-primary" />
                         <span className="text-primary font-medium">{aiStatus}</span>
                      </div>
                    ) : isAiTyping ? (
                      <span className="text-muted-foreground">AI正在思考...</span>
                    ) : (
                      '输入指令或 @ 选择专属助手'
                    )}
                  </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            {/* A5: 移动端显示关闭按钮 */}
            {isMobile && isExpanded ? (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                data-compact
                onClick={onToggle}
              >
                <X className="w-4 h-4" />
              </Button>
            ) : (
              <>
                {variant === 'overlay' && isExpanded && (
                  <>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          data-compact
                          onClick={(e) => {
                            e.stopPropagation();
                            setIsFullscreen(!isFullscreen);
                          }}
                        >
                          {isFullscreen ? (
                            <Minimize2 className="w-4 h-4" />
                          ) : (
                            <Maximize2 className="w-4 h-4" />
                          )}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {isFullscreen ? '退出全屏' : '全屏模式'}
                      </TooltipContent>
                    </Tooltip>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          data-compact
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Settings className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={handleClearChat}>
                          <Trash2 className="w-4 h-4 mr-2" />
                          清空对话
                        </DropdownMenuItem>
                        <DropdownMenuItem>
                          <Download className="w-4 h-4 mr-2" />
                          导出对话
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem>
                          <History className="w-4 h-4 mr-2" />
                          历史记录
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </>
                )}

                {isFullscreen ? (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    data-compact
                    onClick={() => {
                      setIsFullscreen(false);
                      onToggle();
                    }}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                ) : (
                  <button className="p-2 rounded-lg hover:bg-secondary transition-colors">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5" />
                    ) : (
                      <ChevronUp className="w-5 h-5" />
                    )}
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Chat Area */}
        {(isExpanded || variant === 'embedded') && (
          <div className={cn(
            'flex flex-col flex-1 min-h-0', // min-h-0 important for flex nesting
            variant === 'overlay' && isFullscreen ? 'h-[calc(100dvh-4rem)]' : '',
            variant === 'overlay' && !isFullscreen ? 'h-[calc(85dvh-4rem)] md:h-[436px]' : ''
          )}>
            {/* Messages */}
            <ScrollArea className="flex-1 px-4 md:px-6">
              <div className="py-4 space-y-4">
                {messages.map((msg, index) => (
                  <MessageBubble
                    key={msg.id}
                    message={msg}
                    onCopy={handleCopy}
                    onRegenerate={
                      index === messages.length - 1 && msg.role === 'assistant'
                        ? handleRegenerate
                        : undefined
                    }
                    onFeedback={(type) => {
                      if (import.meta.env.DEV) console.log('Feedback:', type, msg.id);
                    }}
                    onDelete={() => handleDeleteMessage(msg.id)}
                    isLatest={index === messages.length - 1}
                    isTyping={isAiTyping}
                  />
                ))}
                
                {isAiTyping && aiStatus && (
                   <div className="flex items-center gap-2 px-4 py-2 mb-2 text-xs text-muted-foreground bg-secondary/30 rounded-lg mx-4 animate-pulse w-fit">
                     <Loader2 className="w-3 h-3 animate-spin text-primary" />
                     <span className="font-mono">{aiStatus}</span>
                   </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            {/* Quick Replies */}
            {showQuickReplies && messages.length <= 1 && (
              <div className="px-4 md:px-6 py-2 border-t border-border/50">
                <p className="text-xs text-muted-foreground mb-2">快捷指令</p>
                <div className="flex flex-wrap gap-2">
                  {defaultQuickReplies.map((reply) => (
                    <Button
                      key={reply.id}
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs"
                      onClick={() => handleQuickReply(reply)}
                    >
                      {reply.icon}
                      <span className="ml-1.5">{reply.text}</span>
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Input Area - A5: 添加安全区适配 */}
            {quotaAlert && (
              <div className={cn(
                'mx-4 md:mx-6 mb-1 px-3 py-2 rounded-lg text-xs flex items-center gap-2',
                quotaAlert.alert_level === 'exhausted' && 'bg-destructive/10 text-destructive border border-destructive/20',
                quotaAlert.alert_level === 'critical' && 'bg-orange-500/10 text-orange-600 border border-orange-500/20',
                quotaAlert.alert_level === 'warning' && 'bg-yellow-500/10 text-yellow-600 border border-yellow-500/20',
              )}>
                <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                <span className="flex-1">{quotaAlert.alert_message}</span>
                <button
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => setQuotaAlert(null)}
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            )}
            <div className="px-4 md:px-6 py-4 border-t border-border bg-card sticky bottom-0 pb-[calc(1rem+env(safe-area-inset-bottom))]">
              {/* Agent Tags */}
              {showAgents && (
                <div className="mb-3 p-2 bg-secondary/50 rounded-lg animate-fade-slide-up">
                  <p className="text-xs text-muted-foreground mb-2">选择AI助手</p>
                  <div className="grid grid-cols-2 gap-2">
                    {agentTags.map((agent) => (
                      <button
                        key={agent.id}
                        onClick={() => insertAgent(agent)}
                        className={cn(
                          'flex items-start gap-2 p-2 rounded-lg text-left transition-colors',
                          'hover:bg-secondary',
                          agent.color
                        )}
                      >
                        <span className="mt-0.5">{agent.icon}</span>
                        <div>
                          <p className="text-xs font-medium">{agent.name}</p>
                          <p className="text-[10px] text-muted-foreground">
                            {agent.description}
                          </p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2">
                {/* Mobile-only: collapsed + menu for @agent, attachment, mic */}
                <div className="flex sm:hidden">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-10 w-10 flex-shrink-0" data-compact>
                        <Plus className="w-5 h-5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start">
                      <DropdownMenuItem onClick={() => setShowAgents(!showAgents)}>
                        <AtSign className="w-4 h-4 mr-2" /> 选择AI助手
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => fileInputRef.current?.click()}>
                        <Paperclip className="w-4 h-4 mr-2" /> 上传文档
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={toggleRecording}>
                        <Mic className="w-4 h-4 mr-2" /> 语音输入
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                {/* Desktop-only: @agent and attachment buttons */}
                <div className="hidden sm:flex items-center gap-2">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant={showAgents ? 'default' : 'ghost'}
                        size="icon"
                        className="h-10 w-10 flex-shrink-0"
                        onClick={() => setShowAgents(!showAgents)}
                      >
                        <AtSign className="w-5 h-5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>选择AI助手</TooltipContent>
                  </Tooltip>

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-10 w-10 flex-shrink-0"
                        onClick={() => fileInputRef.current?.click()}
                      >
                        <Paperclip className="w-5 h-5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>上传文档</TooltipContent>
                  </Tooltip>
                </div>

                {/* Hidden file input (shared by mobile and desktop) */}
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  onChange={handleFileUpload}
                  accept=".pdf,.txt,.md,.csv,.json,.docx"
                />

                <div className="flex-1 relative">
                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                    placeholder={
                      currentAgent
                        ? `向 ${currentAgent} 提问...`
                        : '输入指令... 按 @ 选择助手'
                    }
                    className="w-full bg-secondary rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
                    disabled={isAiTyping}
                  />
                  {currentAgent && (
                    <Badge
                      variant="secondary"
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px]"
                    >
                      {currentAgent}
                      <button
                        className="ml-1 hover:text-foreground"
                        onClick={() => setCurrentAgent(undefined)}
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </Badge>
                  )}
                </div>

                {/* Desktop-only: mic button */}
                <div className="hidden sm:block">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant={isRecording ? 'destructive' : 'ghost'}
                        size="icon"
                        className={cn(
                          'h-10 w-10 flex-shrink-0 relative',
                          isRecording && 'animate-pulse'
                        )}
                        onClick={toggleRecording}
                      >
                        {isRecording && (
                          <span className="absolute inset-0 rounded-md bg-red-500/20 animate-ping" />
                        )}
                        {isRecording ? (
                          <MicOff className="w-5 h-5 relative z-10" />
                        ) : (
                          <Mic className="w-5 h-5" />
                        )}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {isRecording ? '停止录音' : '语音输入'}
                    </TooltipContent>
                  </Tooltip>
                </div>

                <Button
                  size="icon"
                  className={cn(
                    'h-10 w-10 flex-shrink-0 transition-all',
                    input.trim() && !isAiTyping
                      ? 'bg-primary hover:bg-primary/90 shadow-lg'
                      : 'bg-secondary text-muted-foreground'
                  )}
                  onClick={handleSend}
                  disabled={!input.trim() || isAiTyping}
                >
                  {isAiTyping ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </Button>
              </div>

              <p className="text-[10px] text-muted-foreground mt-2 text-center hidden md:block">
                按 <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Enter</kbd> 发送
                {' · '}
                <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">@</kbd> 选择助手
                {' · '}
                <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">⌘K</kbd> 命令面板
              </p>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default EnhancedAIChatPanel;
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
} from 'lucide-react';
import { AIMessage } from '@/types/nexus';
import { toast } from 'sonner';
import { useAIStream } from '@/hooks/useAIStream';
import { PulseDot } from '@/components/common/AnimatedComponents';
import { MessageBubble } from './MessageBubble';


// ==================== 类型定义 ====================

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
}: EnhancedAIChatPanelProps) {
  const { user } = useUser();
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [input, setInput] = useState('');
  const [showAgents, setShowAgents] = useState(false);
  const [showQuickReplies, setShowQuickReplies] = useState(true);
  const [currentAgent, setCurrentAgent] = useState<string | undefined>(defaultAgent);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { isTyping: isAiTyping, aiStatus, streamChat } = useAIStream({ userId: user.id });

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
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'https://aizhz.zeabur.app';
      const response = await fetch(`${baseUrl}/api/documents/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Upload failed');

      const result = await response.json();
      toast.success(
        `文档 "${file.name}" 已存入知识库 (处理了 ${result.details[0]?.chunks_processed || 0} 个片段)`,
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

  const toggleRecording = () => {
    setIsRecording(!isRecording);
    if (!isRecording) {
      toast.info('语音输入功能即将上线');
    }
  };

  const panelHeightClass = useMemo(() => {
    if (isFullscreen) return 'h-screen';
    if (isExpanded) return 'h-[85vh] md:h-[500px]';
    return 'h-16';
  }, [isExpanded, isFullscreen]);

  return (
    <>
      {isExpanded && !isFullscreen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 md:hidden"
          onClick={onToggle}
        />
      )}

      <div
        className={cn(
          'fixed bg-card border-t border-border transition-all duration-300 z-50 shadow-[0_-4px_20px_-1px_rgba(0,0,0,0.1)]',
          isFullscreen
            ? 'inset-0 rounded-none'
            : 'bottom-0 left-0 right-0 md:left-64 md:right-80 rounded-t-2xl md:rounded-none',
          panelHeightClass
        )}
      >
        {/* Header */}
        <div
          className={cn(
            'h-16 px-4 md:px-6 flex items-center justify-between cursor-pointer hover:bg-card-elevated/50 transition-colors',
            isFullscreen ? 'rounded-none' : 'rounded-t-2xl md:rounded-t-none'
          )}
          onClick={!isFullscreen ? onToggle : undefined}
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
              <p className="text-xs text-muted-foreground flex items-center gap-2">
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
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            {isExpanded && (
              <>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
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
          </div>
        </div>

        {/* Chat Area */}
        {isExpanded && (
          <div className={cn(
            'flex flex-col',
            isFullscreen ? 'h-[calc(100vh-4rem)]' : 'h-[calc(85vh-4rem)] md:h-[436px]'
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
                      console.log('Feedback:', type, msg.id);
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

            {/* Input Area */}
            <div className="px-4 md:px-6 py-4 border-t border-border bg-card">
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

                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  onChange={handleFileUpload}
                  accept=".pdf,.txt,.md,.csv,.json,.docx"
                />
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

                <div className="flex-1 relative">
                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
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

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant={isRecording ? 'destructive' : 'ghost'}
                      size="icon"
                      className="h-10 w-10 flex-shrink-0"
                      onClick={toggleRecording}
                    >
                      {isRecording ? (
                        <MicOff className="w-5 h-5" />
                      ) : (
                        <Mic className="w-5 h-5" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {isRecording ? '停止录音' : '语音输入'}
                  </TooltipContent>
                </Tooltip>

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
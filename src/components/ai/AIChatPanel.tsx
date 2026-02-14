import React, { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useUser } from '@/contexts/UserContext';
import { supabase } from '@/integrations/supabase/client';
import {
  Bot,
  ChevronUp,
  ChevronDown,
  Send,
  Mic,
  Sparkles,
  AtSign,
  Loader2,
  Paperclip,
} from 'lucide-react';
import { AIMessage, ThinkingStep } from '@/types/nexus';
import { toast } from 'sonner';
import { ThinkingChain } from './ThinkingChain';

const agentTags = [
  { id: 'sales', name: '@销售指挥官', color: 'text-primary' },
  { id: 'performance', name: '@绩效教练', color: 'text-success' },
  { id: 'approval', name: '@企业小助手', color: 'text-warning' },
  { id: 'knowledge', name: '@知识助手', color: 'text-purple-400' },
];

interface AIChatPanelProps {
  isExpanded: boolean;
  onToggle: () => void;
}

import { useAIStream } from '@/hooks/useAIStream';

export function AIChatPanel({ isExpanded, onToggle }: AIChatPanelProps) {
  const { user } = useUser();
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [input, setInput] = useState('');
  const [showAgents, setShowAgents] = useState(false);
  const [currentAgent, setCurrentAgent] = useState<string | undefined>();
  const [currentThinkingSteps, setCurrentThinkingSteps] = useState<ThinkingStep[]>([]);
  const [showThinkingChain, setShowThinkingChain] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { isTyping: isAiTyping, aiStatus, thinkingSteps, isThinkingComplete, streamChat, clearThinkingSteps } = useAIStream({ userId: user.id });

  // Sync thinking steps from hook
  useEffect(() => {
    setCurrentThinkingSteps(thinkingSteps);
  }, [thinkingSteps]);

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
      // P0 Security Fix: Attach auth token for file upload
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) {
        toast.error('请先登录后再上传文档');
        toast.dismiss(toastId);
        return;
      }

      // Construct upload URL (simplifying based on existing logic)
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
      toast.success(`文档 "${file.name}" 已存入知识库 (处理了 ${result.details[0]?.chunks_processed || 0} 个片段)`);

      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `System: 用户上传了新文档 "${file.name}" 到知识库。`,
        timestamp: new Date(),
        agent: '@知识助手'
      }]);

    } catch (error) {
      console.error(error);
      toast.error('文档上传失败');
    } finally {
      toast.dismiss(toastId);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  useEffect(() => {
    const greeting = user.role === 'boss' ? (
      {
        id: '1',
        role: 'assistant',
        content: `早上好，${user.name}！📊\n\n今日AI摘要：\n• 3条异常审批待您确认（均已超时预警）\n• 本周销售激励已自动发放 ¥12,800\n• 团队整体赢率提升 8.5%\n\n无需其他操作，一切尽在掌控。有什么需要了解的？`,
        timestamp: new Date(Date.now() - 1000 * 60 * 5),
        agent: '@企业小助手',
      }
    ) : (
      {
        id: '1',
        role: 'assistant',
        content: `早上好，${user.name}！我是您的AI指挥官 🚀\n\n今日重点：\n• 张教授商机进入关键阶段，建议上午跟进\n• 您的绩效分已达87分，距离"销售精英"徽章仅差13分\n• 有1条新线索待查看\n\n有什么我可以帮您的？`,
        timestamp: new Date(Date.now() - 1000 * 60 * 5),
        agent: '@销售指挥官',
      }
    );
    setMessages([greeting as AIMessage]);
  }, [user.role, user.name]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isAiTyping) return;

    const userMessage: AIMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    const messageToSend = input;
    setInput('');
    clearThinkingSteps();
    setCurrentThinkingSteps([]);

    // Detect agent
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
        {
          onUpdate: (content, assistantMsgId) => {
            setMessages(prev => {
              const exists = prev.find(m => m.id === assistantMsgId);
              if (exists) {
                return prev.map(m => m.id === assistantMsgId ? { ...m, content, thinkingSteps: currentThinkingSteps } : m);
              } else {
                return [...prev, {
                  id: assistantMsgId,
                  role: 'assistant',
                  content,
                  timestamp: new Date(),
                  agent: detectedAgent,
                  thinkingSteps: currentThinkingSteps
                }];
              }
            });
          },
          onThinkingStep: (step) => {
            setCurrentThinkingSteps(prev => [...prev, step]);
          },
          onThinkingComplete: () => {
            // Thinking chain is complete
          }
        }
      );
    } catch (e) {
      // Error already toasted in hook
      setMessages(prev => prev.filter(m => m.content !== ''));
    }
  };

  const insertAgent = (agentName: string) => {
    setInput(prev => prev + agentName + ' ');
    setCurrentAgent(agentName);
    setShowAgents(false);
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isExpanded && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 md:hidden animate-fade-in"
          onClick={onToggle}
        />
      )}

      <div
        className={cn(
          "fixed bottom-0 bg-card border-t border-border transition-all duration-300 z-50 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]",
          // Mobile Styles: Full width, rounded top corners when expanded
          "left-0 right-0",
          isExpanded ? "h-[85vh] rounded-t-2xl" : "h-16",

          // Desktop Styles: Respect sidebar and right panel
          "md:left-64 md:right-80 md:rounded-none",
          isExpanded ? "md:h-96" : "md:h-16"
        )}
      >
        {/* Header */}
        <div
          className="h-16 px-4 md:px-6 flex items-center justify-between cursor-pointer hover:bg-card-elevated transition-colors rounded-t-2xl md:rounded-t-none"
          onClick={onToggle}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center animate-pulse-glow">
              <Bot className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground flex items-center gap-2">
                AI 指挥中心
                <Sparkles className="w-4 h-4 text-primary" />
              </h3>
              <p className="text-xs text-muted-foreground flex items-center gap-2">
                {aiStatus ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin text-primary" />
                    <span className="text-primary animate-pulse">{aiStatus}</span>
                  </>
                ) : (
                  isAiTyping ? 'AI正在输入...' : '输入指令或自然语言对话'
                )}
              </p>
            </div>
          </div>
          <button className="p-2 rounded-lg hover:bg-secondary transition-colors">
            {isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronUp className="w-5 h-5" />}
          </button>
        </div>

        {/* Chat Area */}
        {isExpanded && (
          <div className="h-80 flex flex-col">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
              {messages.map((msg) => (
                <div key={msg.id}>
                  <div
                    className={cn(
                      "flex gap-3",
                      msg.role === 'user' ? "justify-end" : "justify-start"
                    )}
                  >
                    {msg.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-lg bg-gradient-primary flex items-center justify-center flex-shrink-0">
                        <Bot className="w-4 h-4 text-primary-foreground" />
                      </div>
                    )}
                    <div
                      className={cn(
                        "max-w-md rounded-2xl px-4 py-3",
                        msg.role === 'user'
                          ? "bg-primary text-primary-foreground rounded-br-md"
                          : "bg-secondary text-foreground rounded-bl-md"
                      )}
                    >
                      {msg.agent && msg.role === 'assistant' && (
                        <p className="text-xs text-primary font-medium mb-1">{msg.agent}</p>
                      )}
                      <p className="text-sm whitespace-pre-line">{msg.content}</p>
                    </div>
                  </div>
                  {/* Show thinking chain for assistant messages */}
                  {msg.role === 'assistant' && msg.thinkingSteps && msg.thinkingSteps.length > 0 && showThinkingChain && (
                    <div className="ml-11 mt-2">
                      <ThinkingChain
                        steps={msg.thinkingSteps}
                        isComplete={true}
                        isStreaming={false}
                      />
                    </div>
                  )}
                </div>
              ))}
              {/* Current streaming thinking chain */}
              {isAiTyping && currentThinkingSteps.length > 0 && showThinkingChain && (
                <div className="ml-11">
                  <ThinkingChain
                    steps={currentThinkingSteps}
                    isComplete={isThinkingComplete}
                    isStreaming={!isThinkingComplete}
                  />
                </div>
              )}
              {isAiTyping && messages[messages.length - 1]?.content === '' && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-primary flex items-center justify-center">
                    <Bot className="w-4 h-4 text-primary-foreground" />
                  </div>
                  <div className="bg-secondary rounded-2xl rounded-bl-md px-4 py-3">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="px-6 py-4 border-t border-border">
              {/* Agent Tags */}
              {showAgents && (
                <div className="flex gap-2 mb-3 animate-fade-in">
                  {agentTags.map((agent) => (
                    <button
                      key={agent.id}
                      onClick={() => insertAgent(agent.name)}
                      className={cn(
                        "px-3 py-1.5 rounded-full text-xs font-medium bg-secondary hover:bg-secondary/80 transition-colors",
                        agent.color
                      )}
                    >
                      {agent.name}
                    </button>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowAgents(!showAgents)}
                  className={cn(
                    "p-2 rounded-lg transition-colors",
                    showAgents ? "bg-primary text-primary-foreground" : "hover:bg-secondary text-muted-foreground"
                  )}
                >
                  <AtSign className="w-5 h-5" />
                </button>
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  onChange={handleFileUpload}
                  accept=".pdf,.txt,.md,.csv,.json"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="p-2 rounded-lg hover:bg-secondary text-muted-foreground transition-colors"
                >
                  <Paperclip className="w-5 h-5" />
                </button>
                <div className="flex-1 relative">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="输入指令... 例如：帮我分析张教授商机"
                    className="w-full bg-secondary rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                    disabled={isAiTyping}
                  />
                </div>
                <button className="p-2 rounded-lg hover:bg-secondary text-muted-foreground transition-colors">
                  <Mic className="w-5 h-5" />
                </button>
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isAiTyping}
                  className={cn(
                    "p-3 rounded-xl transition-all",
                    input.trim() && !isAiTyping
                      ? "bg-gradient-primary text-primary-foreground glow-primary"
                      : "bg-secondary text-muted-foreground"
                  )}
                >
                  {isAiTyping ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

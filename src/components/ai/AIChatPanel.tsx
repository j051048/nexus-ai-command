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
} from 'lucide-react';
import { AIMessage } from '@/types/nexus';
import { toast } from 'sonner';

const agentTags = [
  { id: 'sales', name: '@销售指挥官', color: 'text-primary' },
  { id: 'performance', name: '@绩效教练', color: 'text-success' },
  { id: 'approval', name: '@审批管家', color: 'text-warning' },
  { id: 'knowledge', name: '@知识助手', color: 'text-purple-400' },
];

const initialMessages: AIMessage[] = [
  {
    id: '1',
    role: 'assistant',
    content: '早上好！我是您的AI指挥官 🚀\n\n今日重点：\n• 张教授商机进入关键阶段，建议上午跟进\n• 您的绩效分已达87分，距离"销售精英"徽章仅差13分\n• 有1条新线索待查看\n\n有什么我可以帮您的？',
    timestamp: new Date(Date.now() - 1000 * 60 * 5),
    agent: '@销售指挥官',
  },
];

const bossInitialMessages: AIMessage[] = [
  {
    id: '1',
    role: 'assistant',
    content: '早上好，李总！📊\n\n今日AI摘要：\n• 3条异常审批待您确认（均已超时预警）\n• 本周销售激励已自动发放 ¥12,800\n• 团队整体赢率提升 8.5%\n\n无需其他操作，一切尽在掌控。有什么需要了解的？',
    timestamp: new Date(Date.now() - 1000 * 60 * 5),
    agent: '@审批管家',
  },
];

interface AIChatPanelProps {
  isExpanded: boolean;
  onToggle: () => void;
}

export function AIChatPanel({ isExpanded, onToggle }: AIChatPanelProps) {
  const { user } = useUser();
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showAgents, setShowAgents] = useState(false);
  const [currentAgent, setCurrentAgent] = useState<string | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setMessages(user.role === 'boss' ? bossInitialMessages : initialMessages);
  }, [user.role]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const streamChat = async (userMessage: string) => {
    // Check for agent mention in message
    let detectedAgent = currentAgent;
    for (const agent of agentTags) {
      if (userMessage.includes(agent.name)) {
        detectedAgent = agent.name;
        break;
      }
    }

    const chatMessages = messages
      .filter(m => m.id !== '1') // Skip initial greeting for context
      .map(m => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      }));

    chatMessages.push({ role: 'user', content: userMessage });

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/chat`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            // 'Authorization': `Bearer ${token}` // If backend implements auth
          },
          body: JSON.stringify({
            messages: chatMessages,
            agent: detectedAgent,
            userId: user.id
          }),
          signal: abortControllerRef.current.signal,
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `请求失败: ${response.status}`);
      }

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let textBuffer = '';
      let assistantContent = '';

      // Create assistant message placeholder
      const assistantMsgId = Date.now().toString();
      setMessages(prev => [
        ...prev,
        {
          id: assistantMsgId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          agent: detectedAgent,
        },
      ]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        textBuffer += decoder.decode(value, { stream: true });

        let newlineIndex: number;
        while ((newlineIndex = textBuffer.indexOf('\n')) !== -1) {
          let line = textBuffer.slice(0, newlineIndex);
          textBuffer = textBuffer.slice(newlineIndex + 1);

          if (line.endsWith('\r')) line = line.slice(0, -1);
          if (line.startsWith(':') || line.trim() === '') continue;
          if (!line.startsWith('data: ')) continue;

          const jsonStr = line.slice(6).trim();
          if (jsonStr === '[DONE]') break;

          try {
            const parsed = JSON.parse(jsonStr);
            const content = parsed.choices?.[0]?.delta?.content as string | undefined;
            if (content) {
              assistantContent += content;
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantMsgId ? { ...m, content: assistantContent } : m
                )
              );
            }
          } catch {
            // Incomplete JSON, put back and wait for more
            textBuffer = line + '\n' + textBuffer;
            break;
          }
        }
      }

      // Final flush
      if (textBuffer.trim()) {
        for (let raw of textBuffer.split('\n')) {
          if (!raw) continue;
          if (raw.endsWith('\r')) raw = raw.slice(0, -1);
          if (raw.startsWith(':') || raw.trim() === '') continue;
          if (!raw.startsWith('data: ')) continue;
          const jsonStr = raw.slice(6).trim();
          if (jsonStr === '[DONE]') continue;
          try {
            const parsed = JSON.parse(jsonStr);
            const content = parsed.choices?.[0]?.delta?.content as string | undefined;
            if (content) {
              assistantContent += content;
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantMsgId ? { ...m, content: assistantContent } : m
                )
              );
            }
          } catch {
            /* ignore */
          }
        }
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') return;
      console.error('AI chat error:', error);
      toast.error((error as Error).message || 'AI 回复失败，请重试');
      // Remove empty assistant message on error
      setMessages(prev => prev.filter(m => m.content !== ''));
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    const userMessage: AIMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    const messageToSend = input;
    setInput('');
    setIsTyping(true);

    await streamChat(messageToSend);
    setIsTyping(false);
  };

  const insertAgent = (agentName: string) => {
    setInput(prev => prev + agentName + ' ');
    setCurrentAgent(agentName);
    setShowAgents(false);
  };

  return (
    <div
      className={cn(
        "fixed bottom-0 left-64 right-80 bg-card border-t border-border transition-all duration-300 z-50",
        isExpanded ? "h-96" : "h-16"
      )}
    >
      {/* Header */}
      <div
        className="h-16 px-6 flex items-center justify-between cursor-pointer hover:bg-card-elevated transition-colors"
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
            <p className="text-xs text-muted-foreground">
              {isTyping ? 'AI正在输入...' : '输入指令或自然语言对话'}
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
              <div
                key={msg.id}
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
            ))}
            {isTyping && messages[messages.length - 1]?.content === '' && (
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
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                  placeholder="输入指令... 例如：帮我分析张教授商机"
                  className="w-full bg-secondary rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                  disabled={isTyping}
                />
              </div>
              <button className="p-2 rounded-lg hover:bg-secondary text-muted-foreground transition-colors">
                <Mic className="w-5 h-5" />
              </button>
              <button
                onClick={handleSend}
                disabled={!input.trim() || isTyping}
                className={cn(
                  "p-3 rounded-xl transition-all",
                  input.trim() && !isTyping
                    ? "bg-gradient-primary text-primary-foreground glow-primary"
                    : "bg-secondary text-muted-foreground"
                )}
              >
                {isTyping ? (
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
  );
}

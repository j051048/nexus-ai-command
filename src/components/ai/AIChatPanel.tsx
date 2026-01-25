import React, { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useUser } from '@/contexts/UserContext';
import {
  Bot,
  ChevronUp,
  ChevronDown,
  Send,
  Mic,
  Sparkles,
  AtSign,
} from 'lucide-react';
import { AIMessage } from '@/types/nexus';

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
    content: '早上好！我是您的AI指挥官 🚀\n\n今日重点：\n• 张教授商机进入关键阶段，建议上午跟进\n• 您的绩效分已达87分，距离"销售精英"徽章仅差13分\n• 有1条新线索待查看',
    timestamp: new Date(Date.now() - 1000 * 60 * 5),
    agent: '@销售指挥官',
  },
];

const bossInitialMessages: AIMessage[] = [
  {
    id: '1',
    role: 'assistant',
    content: '早上好，李总！📊\n\n今日AI摘要：\n• 3条异常审批待您确认（均已超时预警）\n• 本周销售激励已自动发放 ¥12,800\n• 团队整体赢率提升 8.5%\n\n无需其他操作，一切尽在掌控。',
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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(user.role === 'boss' ? bossInitialMessages : initialMessages);
  }, [user.role]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage: AIMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    // Simulate AI response
    setTimeout(() => {
      const aiResponse: AIMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: generateAIResponse(input, user.role),
        timestamp: new Date(),
        agent: '@销售指挥官',
      };
      setMessages(prev => [...prev, aiResponse]);
      setIsTyping(false);
    }, 1500);
  };

  const generateAIResponse = (input: string, role: string): string => {
    const lowerInput = input.toLowerCase();
    
    if (lowerInput.includes('出差') || lowerInput.includes('差旅')) {
      return '已为您创建出差申请 ✅\n\n📍 目的地：上海\n💰 预算：¥2,500（高铁+酒店）\n📅 时间：下周\n\n系统判断：符合预算标准，已自动审批通过！预订信息稍后发送至您邮箱。';
    }
    
    if (lowerInput.includes('张教授') || lowerInput.includes('跟进')) {
      return '张教授（北大物理系）商机分析 📊\n\n当前阶段：技术验证\nAI赢率预测：78%\n建议行动：\n1. 今日下午3点是最佳联系时间\n2. 建议提及上周演示的光谱精度数据\n3. 准备好竞品对比材料\n\n需要我生成跟进邮件吗？';
    }
    
    if (lowerInput.includes('奖金') || lowerInput.includes('激励')) {
      return '您的激励账户 💰\n\n本月累计：¥4,850\n待提现：¥2,200\n\n最近获得：\n• +¥300 张教授商机推进\n• +¥200 连续5日跟进达标\n• +¥150 通话质量评分90+\n\n继续加油！距离本月目标还差 ¥1,150';
    }
    
    return '收到！我正在处理您的请求...\n\n如需更精准的帮助，可以@指定的AI助手：\n• @销售指挥官 - 销售策略与线索\n• @绩效教练 - 绩效分析与激励\n• @审批管家 - 各类审批处理\n• @知识助手 - 产品与竞品知识';
  };

  const insertAgent = (agentName: string) => {
    setInput(prev => prev + agentName + ' ');
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
            {isTyping && (
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
                />
              </div>
              <button className="p-2 rounded-lg hover:bg-secondary text-muted-foreground transition-colors">
                <Mic className="w-5 h-5" />
              </button>
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className={cn(
                  "p-3 rounded-xl transition-all",
                  input.trim()
                    ? "bg-gradient-primary text-primary-foreground glow-primary"
                    : "bg-secondary text-muted-foreground"
                )}
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

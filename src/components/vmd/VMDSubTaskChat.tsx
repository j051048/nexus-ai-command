import React, { useState, useRef, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Send, Bot, Loader2, CheckCircle2 } from 'lucide-react';
import { useAIStream } from '@/hooks/useAIStream';
import { useSubmitSubTask } from '@/hooks/useVMD';
import { useUser } from '@/contexts/UserContext';
import { AIMessage } from '@/types/nexus';
import { VMDSubTask } from '@/hooks/useVMD';
import { cn } from '@/lib/utils';

interface VMDSubTaskChatProps {
  subTask: VMDSubTask | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sceneCode: string; // From the main task
}

export function VMDSubTaskChat({
  subTask,
  open,
  onOpenChange,
  sceneCode,
}: VMDSubTaskChatProps) {
  const { user } = useUser();
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { isTyping: isAiTyping, aiStatus, streamChat } = useAIStream({ userId: user?.id || 'default' });
  const submitSubTask = useSubmitSubTask();

  // Initialize chat when opened
  useEffect(() => {
    if (open && subTask) {
      setMessages([
        {
          id: 'greeting',
          role: 'assistant',
          content: `你好！我是负责 [${subTask.agent_role}] 岗位的虚拟员工。我看到我们要处理的子任务是：\n\n**${subTask.title}**\n\n描述: ${subTask.description}\n\n我已经准备好了。请随时给我下达具体命令或者上传补充资料，我会跟您协作完成！\n当您满意我的方案时，可以点击下方的「采纳并完结此环节」。`,
          timestamp: new Date(),
          agent: subTask.agent_role,
        },
      ]);
    } else {
      setMessages([]);
      setInput('');
    }
  }, [open, subTask]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isAiTyping || !subTask) return;

    const userMessage: AIMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    const messageToSend = input;
    setInput('');

    try {
      await streamChat(
        messageToSend,
        newMessages,
        subTask.agent_role,
        {
          onUpdate: (content, assistantMsgId) => {
            setMessages(prev => {
              const exists = prev.find(m => m.id === assistantMsgId);
              if (exists) {
                return prev.map(m => m.id === assistantMsgId ? { ...m, content } : m);
              } else {
                return [...prev, {
                  id: assistantMsgId,
                  role: 'assistant',
                  content,
                  timestamp: new Date(),
                  agent: subTask.agent_role,
                }];
              }
            });
          }
        },
        { 
          vmd_agent_code: subTask.agent_role,
          scene_code: sceneCode
        }
      );
    } catch (e) {
      // Error already handled in hook
      setMessages(prev => prev.filter(m => m.content !== ''));
    }
  };

  const handleComplete = () => {
    if (!subTask) return;
    
    // Auto-extract the last assistant message as the final output
    const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant');
    const finalOutput = lastAssistantMessage?.content || '（暂无AI最终输出记录，已手动采纳完结）';

    submitSubTask.mutate(
      { subTaskId: subTask.id, output: finalOutput },
      {
        onSuccess: () => {
          onOpenChange(false);
        }
      }
    );
  };

  if (!subTask) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px] h-[85vh] flex flex-col p-0 gap-0 overflow-hidden bg-card border-border">
        {/* Header */}
        <DialogHeader className="p-4 md:p-6 border-b border-border bg-card/50 backdrop-blur-xl">
          <DialogTitle className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-primary" />
            <span className="font-semibold">{subTask.title} (与 {subTask.agent_role} 协作中)</span>
          </DialogTitle>
        </DialogHeader>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4 space-y-4">
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
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}
          {isAiTyping && messages[messages.length - 1]?.content === '' && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-lg bg-gradient-primary flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-primary-foreground" />
              </div>
              <div className="bg-secondary text-foreground rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-2">
                 <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                 <span className="text-sm text-muted-foreground">{aiStatus || 'AI正在思考...'}</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 md:p-6 border-t border-border bg-card">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="发送消息与AI协作..."
              className="flex-1 bg-secondary rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              disabled={isAiTyping || submitSubTask.isPending}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isAiTyping || submitSubTask.isPending}
              className={cn(
                "p-3 rounded-xl transition-all",
                input.trim() && !isAiTyping
                  ? "bg-gradient-primary text-primary-foreground glow-primary"
                  : "bg-secondary text-muted-foreground"
              )}
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          
          <div className="mt-4 pt-4 border-t border-border flex justify-end">
            <Button 
               onClick={handleComplete} 
               disabled={isAiTyping || submitSubTask.isPending}
               className="bg-green-600 hover:bg-green-700 text-white gap-2 flex items-center"
            >
              {submitSubTask.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              采纳并完结此环节
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

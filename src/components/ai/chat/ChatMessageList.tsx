import React, { useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Loader2,
  AlertTriangle,
  Zap,
  MessageCircle,
} from 'lucide-react';
import { AIMessage } from '@/types/nexus';
import { MessageBubble } from '../MessageBubble';
import { AgentTracePanel } from '../AgentTracePanel';
import type { ConfirmationRequest, AskUserRequest } from '@/hooks/useAIStream';
import type { AgentTrace } from '@/hooks/useAgentTrace';
import { aiClient } from '@/api/aiClient';

interface ChatMessageListProps {
  messages: AIMessage[];
  setMessages: React.Dispatch<React.SetStateAction<AIMessage[]>>;
  isAiTyping: boolean;
  aiStatus: string | undefined;
  userId: string;
  handleCopy: (content: string) => void;
  handleRegenerate: () => void;
  handleDeleteMessage: (id: string) => void;
  pendingConfirmation: ConfirmationRequest | null;
  confirmAndResend: (
    messages: AIMessage[],
    onUpdate: (content: string, assistantMsgId: string) => void
  ) => void;
  dismissConfirmation: () => void;
  pendingQuestion: AskUserRequest | null;
  answerQuestion: (
    answer: string,
    messages: AIMessage[],
    onUpdate: (content: string, assistantMsgId: string) => void
  ) => void;
  dismissQuestion: () => void;
  showTrace: boolean;
  setShowTrace: (v: boolean) => void;
  trace: AgentTrace;
  messagesEndRef: React.RefObject<HTMLDivElement>;
}

export const ChatMessageList = React.memo(function ChatMessageList({
  messages,
  setMessages,
  isAiTyping,
  aiStatus,
  userId,
  handleCopy,
  handleRegenerate,
  handleDeleteMessage,
  pendingConfirmation,
  confirmAndResend,
  dismissConfirmation,
  pendingQuestion,
  answerQuestion,
  dismissQuestion,
  showTrace,
  setShowTrace,
  trace,
  messagesEndRef,
}: ChatMessageListProps) {
  // Stable feedback callback — avoids creating new function per message per render
  const handleFeedback = useCallback((type: 'positive' | 'negative', msg: AIMessage, index: number) => {
    const sessionId = `chat_${userId}_${Date.now()}`;
    const aiMsg = msg.role === 'assistant' ? msg : undefined;
    const prevUserMsg = index > 0 && messages[index - 1]?.role === 'user' ? messages[index - 1] : undefined;
    aiClient.fetch('/api/v1/ai/feedback', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        message_index: index,
        rating: type,
        ai_response_snippet: aiMsg?.content?.slice(0, 500),
        query_snippet: prevUserMsg?.content?.slice(0, 500),
      }),
    }).catch(() => { /* silent — toast already shown by MessageBubble */ });
  }, [userId, messages]);

  return (
    <ScrollArea className="flex-1 px-4 md:px-6">
      <div className="py-4 space-y-4">
        {messages.map((msg, index) => {
          const isLast = index === messages.length - 1;
          return (
          <MessageBubble
            key={msg.id}
            message={msg}
            onCopy={handleCopy}
            onRegenerate={
              isLast && msg.role === 'assistant'
                ? handleRegenerate
                : undefined
            }
            onFeedback={(type) => handleFeedback(type, msg, index)}
            onDelete={() => handleDeleteMessage(msg.id)}
            isLatest={isLast}
            isTyping={isLast && isAiTyping}
          />
          );
        })}

        {isAiTyping && aiStatus && (
           <div className="flex items-center gap-2 px-4 py-2 mb-2 text-xs text-muted-foreground bg-secondary/30 rounded-lg mx-4 animate-pulse w-fit">
             <Loader2 className="w-3 h-3 animate-spin text-primary" />
             <span className="font-mono">{aiStatus}</span>
           </div>
        )}

        {pendingConfirmation && (
          <div className="mx-4 mb-2 rounded-xl border border-amber-500/30 bg-amber-50 dark:bg-amber-950/20 p-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
              <div className="flex-1 space-y-2">
                <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
                  操作确认
                </p>
                <p className="text-sm text-amber-800 dark:text-amber-300">
                  {pendingConfirmation.message}
                </p>
                {pendingConfirmation.modifiable && pendingConfirmation.args && Object.keys(pendingConfirmation.args).length > 0 && (
                  <details className="pt-1">
                    <summary className="text-xs text-amber-700 dark:text-amber-400 cursor-pointer hover:underline">
                      查看/编辑参数
                    </summary>
                    <pre className="mt-1 p-2 rounded bg-amber-100 dark:bg-amber-900/30 text-xs text-amber-900 dark:text-amber-200 overflow-x-auto max-h-32">
                      {JSON.stringify(pendingConfirmation.args, null, 2)}
                    </pre>
                  </details>
                )}
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    className="h-7 px-3 text-xs"
                    onClick={() => {
                      confirmAndResend(messages, (content, assistantMsgId) => {
                        setMessages((prev) => {
                          const exists = prev.find((m) => m.id === assistantMsgId);
                          if (exists) {
                            return prev.map((m) =>
                              m.id === assistantMsgId ? { ...m, content } : m
                            );
                          }
                          return [...prev, { id: assistantMsgId, role: 'assistant' as const, content, timestamp: new Date() }];
                        });
                      });
                    }}
                  >
                    <Zap className="w-3 h-3 mr-1" />
                    确认执行
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 px-3 text-xs"
                    onClick={dismissConfirmation}
                  >
                    取消
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {pendingQuestion && (
          <div className="mx-4 mb-2 rounded-xl border border-blue-500/30 bg-blue-50 dark:bg-blue-950/20 p-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="flex items-start gap-3">
              <MessageCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 shrink-0" />
              <div className="flex-1 space-y-2">
                <p className="text-sm font-medium text-blue-900 dark:text-blue-200">
                  AI 需要您的输入
                </p>
                <p className="text-sm text-blue-800 dark:text-blue-300">
                  {pendingQuestion.question}
                </p>
                {pendingQuestion.context && (
                  <p className="text-xs text-blue-600 dark:text-blue-400 italic">
                    {pendingQuestion.context}
                  </p>
                )}
                {pendingQuestion.options && pendingQuestion.options.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {pendingQuestion.options.map((option, idx) => (
                      <Button
                        key={idx}
                        size="sm"
                        variant="outline"
                        className="h-7 px-3 text-xs border-blue-300 dark:border-blue-600 hover:bg-blue-100 dark:hover:bg-blue-900/30"
                        onClick={() => {
                          answerQuestion(option, messages, (content, assistantMsgId) => {
                            setMessages((prev) => {
                              const exists = prev.find((m) => m.id === assistantMsgId);
                              if (exists) {
                                return prev.map((m) =>
                                  m.id === assistantMsgId ? { ...m, content } : m
                                );
                              }
                              return [...prev,
                                { id: `user-answer-${Date.now()}`, role: 'user' as const, content: option, timestamp: new Date() },
                                { id: assistantMsgId, role: 'assistant' as const, content, timestamp: new Date() }
                              ];
                            });
                          });
                        }}
                      >
                        {option}
                      </Button>
                    ))}
                  </div>
                )}
                <div className="flex gap-2 pt-1">
                  <input
                    type="text"
                    placeholder="或输入自定义回答..."
                    className="flex-1 h-7 px-2 text-xs rounded border border-blue-300 dark:border-blue-600 bg-white dark:bg-blue-950/30 text-blue-900 dark:text-blue-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.target as HTMLInputElement).value.trim()) {
                        const answer = (e.target as HTMLInputElement).value.trim();
                        answerQuestion(answer, messages, (content, assistantMsgId) => {
                          setMessages((prev) => {
                            const exists = prev.find((m) => m.id === assistantMsgId);
                            if (exists) {
                              return prev.map((m) =>
                                m.id === assistantMsgId ? { ...m, content } : m
                              );
                            }
                            return [...prev,
                              { id: `user-answer-${Date.now()}`, role: 'user' as const, content: answer, timestamp: new Date() },
                              { id: assistantMsgId, role: 'assistant' as const, content, timestamp: new Date() }
                            ];
                          });
                        });
                      }
                    }}
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 px-3 text-xs"
                    onClick={dismissQuestion}
                  >
                    跳过
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {showTrace && (
          <div className="mx-4 mb-2">
            <AgentTracePanel
              trace={trace}
              onClose={() => setShowTrace(false)}
              defaultExpanded
            />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  );
});

import React, { useCallback, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Loader2,
  AlertTriangle,
  Zap,
  MessageCircle,
  Sparkles,
} from 'lucide-react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { AIMessage } from '@/types/nexus';
import { MessageBubble } from '../MessageBubble';
import { AgentTracePanel } from '../AgentTracePanel';
import type { ConfirmationRequest, AskUserRequest, CircuitBreakInfo } from '@/hooks/useAIStream';
import type { AgentTrace } from '@/hooks/useAgentTrace';
import type { OrchestrationTrace } from '@/hooks/useOrchestrationTrace';
import { aiClient } from '@/api/aiClient';
import { ConfirmationCard } from './ConfirmationCard';

import { CapabilityCards } from './CapabilityCards';
import { WorkflowStepper } from './WorkflowStepper';
import { getActivePath, linkMessagesSequentially, getBranchInfo } from '@/lib/messageTree';

const VIRTUAL_THRESHOLD = 30;
const FormBuilder = React.lazy(() => import('../genui/FormBuilder'));

interface ChatMessageListProps {
  messages: AIMessage[];
  setMessages: React.Dispatch<React.SetStateAction<AIMessage[]>>;
  isAiTyping: boolean;
  aiStatus: string | undefined;
  userId: string;
  handleCopy: (content: string) => void;
  handleRegenerate: () => void;
  handleRetry?: () => void;
  handleDeleteMessage: (id: string) => void;
  handleEditMessage?: (messageId: string, newContent: string) => void;
  handleSwitchBranch?: (parentMessageId: string, branchIndex: number) => void;
  pendingConfirmation: ConfirmationRequest | null;
  confirmAndResend: (
    messages: AIMessage[],
    onUpdate: (content: string, assistantMsgId: string) => void,
    modifiedArgs?: Record<string, unknown>
  ) => void;
  dismissConfirmation: () => void;
  pendingQuestion: AskUserRequest | null;
  answerQuestion: (
    answer: string,
    messages: AIMessage[],
    onUpdate: (content: string, assistantMsgId: string) => void
  ) => void;
  dismissQuestion: () => void;
  circuitBreak?: CircuitBreakInfo | null;
  dismissCircuitBreak?: () => void;
  showTrace: boolean;
  setShowTrace: (v: boolean) => void;
  trace: AgentTrace;
  orchestration?: OrchestrationTrace;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  onSendMessage?: (prompt: string) => void;
}

export const ChatMessageList = React.memo(function ChatMessageList({
  messages,
  setMessages,
  isAiTyping,
  aiStatus,
  userId,
  handleCopy,
  handleRegenerate,
  handleRetry,
  handleDeleteMessage,
  handleEditMessage,
  handleSwitchBranch,
  pendingConfirmation,
  confirmAndResend,
  dismissConfirmation,
  pendingQuestion,
  answerQuestion,
  dismissQuestion,
  circuitBreak,
  dismissCircuitBreak,
  showTrace,
  setShowTrace,
  trace,
  orchestration,
  messagesEndRef,
  onSendMessage,
}: ChatMessageListProps) {
  // Use ref for messages to avoid re-creating callback on every messages change
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // Link messages into tree structure (backward compat) and get active path
  const linkedMessages = React.useMemo(() => linkMessagesSequentially(messages), [messages]);
  const activeMessages = React.useMemo(() => getActivePath(linkedMessages), [linkedMessages]);

  // Stable feedback callback — uses ref to avoid messages dependency
  const handleFeedback = useCallback((type: 'positive' | 'negative', messageId: string) => {
    const msgs = messagesRef.current;
    const index = msgs.findIndex(m => m.id === messageId);
    if (index < 0) return;
    const msg = msgs[index];
    const sessionId = `chat_${userId}_${Date.now()}`;
    const aiMsg = msg.role === 'assistant' ? msg : undefined;
    const prevUserMsg = index > 0 && msgs[index - 1]?.role === 'user' ? msgs[index - 1] : undefined;
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
  }, [userId]);

  const useVirtual = activeMessages.length >= VIRTUAL_THRESHOLD;
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: activeMessages.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => 120,
    overscan: 5,
    enabled: useVirtual,
  });

  // Auto-scroll to bottom when new messages arrive (virtual mode)
  useEffect(() => {
    if (useVirtual && activeMessages.length > 0) {
      virtualizer.scrollToIndex(activeMessages.length - 1, { align: 'end' });
    }
  }, [activeMessages.length, useVirtual, virtualizer]);

  // Shared footer content (status, trace, confirmations, etc.)
  const footerContent = (
    <>
      {(isAiTyping || trace.isActive) && !showTrace && (
        <WorkflowStepper 
          steps={trace.steps} 
          isActive={isAiTyping || trace.isActive} 
          onOpenTrace={() => setShowTrace(true)}
        />
      )}

      {isAiTyping && aiStatus && !showTrace && (
         <div className="flex items-center gap-2 px-4 py-2 mb-2 text-xs text-muted-foreground bg-secondary/30 rounded-lg mx-4 animate-pulse w-fit">
           <Loader2 className="w-3 h-3 animate-spin text-primary" />
           <span className="font-mono">{aiStatus}</span>
         </div>
      )}

      {pendingConfirmation && (
        <ConfirmationCard
          confirmation={pendingConfirmation}
          onConfirm={(modifiedArgs) => {
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
            }, modifiedArgs);
          }}
          onDismiss={dismissConfirmation}
        />
      )}

      {pendingQuestion && (
        pendingQuestion.fields && pendingQuestion.fields.length > 0 ? (
          <FormBuilder
            title={pendingQuestion.question}
            fields={pendingQuestion.fields}
            submitLabel="提交"
            onSubmit={(data) => {
              const answer = JSON.stringify(data);
              answerQuestion(answer, messages, (content, assistantMsgId) => {
                setMessages((prev) => {
                  const exists = prev.find((m) => m.id === assistantMsgId);
                  if (exists) {
                    return prev.map((m) =>
                      m.id === assistantMsgId ? { ...m, content } : m
                    );
                  }
                  return [...prev,
                    { id: `user-answer-${Date.now()}`, role: 'user' as const, content: `[表单提交] ${answer}`, timestamp: new Date() },
                    { id: assistantMsgId, role: 'assistant' as const, content, timestamp: new Date() }
                  ];
                });
              });
            }}
          />
        ) : (
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
                <div className="flex flex-wrap gap-2 pt-2">
                  {pendingQuestion.options.map((option, idx) => (
                    <button
                      key={idx}
                      className="inline-flex items-center gap-1.5 h-8 px-4 text-xs font-medium rounded-full border border-blue-200 dark:border-blue-700 bg-white dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 shadow-sm hover:bg-blue-50 dark:hover:bg-blue-900/50 hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md active:scale-[0.97] transition-all duration-150 cursor-pointer"
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
                      <Sparkles className="w-3 h-3 text-blue-400 dark:text-blue-500" />
                      {option}
                    </button>
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
        )
      )}

      {/* Circuit break warning card */}
      {circuitBreak && (
        <div className="mx-4 mb-2 p-3 rounded-lg border border-orange-200 bg-orange-50 dark:bg-orange-950/30 dark:border-orange-800/50">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-orange-500 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-orange-700 dark:text-orange-300">推理已中断</p>
              <p className="text-xs text-orange-600 dark:text-orange-400 mt-1">{circuitBreak.suggestion}</p>
              {dismissCircuitBreak && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs mt-2 text-orange-600 hover:text-orange-700 hover:bg-orange-100 dark:hover:bg-orange-900/30"
                  onClick={dismissCircuitBreak}
                >
                  知道了
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {!isAiTyping && trace.steps.length > 0 && !showTrace && (
        <button
          onClick={() => setShowTrace(true)}
          className="mx-4 mb-2 px-3 py-1.5 text-xs text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-lg transition-colors flex items-center gap-1.5"
        >
          <Zap className="w-3 h-3" />
          查看执行记录 ({trace.steps.length} 步)
        </button>
      )}

      {showTrace && (
        <div className="mx-4 mb-2">
          <AgentTracePanel
            trace={trace}
            orchestration={orchestration}
            onClose={() => setShowTrace(false)}
            defaultExpanded
          />
        </div>
      )}
    </>
  );

  // Virtual rendering for long conversations
  if (useVirtual) {
    return (
      <div 
        ref={scrollContainerRef} 
        className="flex-1 overflow-auto px-4 md:px-6"
        role="log"
        aria-live="polite"
        aria-label="实时聊天记录"
      >
        <div
          className="py-4 relative"
          style={{ height: `${virtualizer.getTotalSize()}px` }}
        >
          {virtualizer.getVirtualItems().map((virtualItem) => {
            const msg = activeMessages[virtualItem.index];
            const isLast = virtualItem.index === activeMessages.length - 1;
            return (
              <div
                key={msg.id}
                data-index={virtualItem.index}
                ref={virtualizer.measureElement}
                className="absolute left-0 right-0 pb-4"
                style={{ transform: `translateY(${virtualItem.start}px)` }}
              >
                <>
                  <MessageBubble
                    message={msg}
                    onCopy={handleCopy}
                    onRegenerate={
                      isLast && msg.role === 'assistant'
                        ? handleRegenerate
                        : undefined
                    }
                    onRetry={msg.status === 'error' ? handleRetry : undefined}
                    onFeedback={handleFeedback}
                    onDelete={handleDeleteMessage}
                    onSendMessage={onSendMessage}
                    onEditMessage={handleEditMessage}
                    onSwitchBranch={handleSwitchBranch}
                    branchInfo={getBranchInfo(linkedMessages, msg.id)}
                    isLatest={isLast}
                    isTyping={isLast && isAiTyping}
                  />
                  {virtualItem.index === 0 && activeMessages.length <= 1 && onSendMessage && (
                    <div className="mt-4 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300 fill-mode-both">
                      <CapabilityCards onSelect={onSendMessage} />
                    </div>
                  )}
                </>
              </div>
            );
          })}
        </div>
        {footerContent}
        <div ref={messagesEndRef} />
      </div>
    );
  }

  // Default rendering for short conversations
  return (
    <ScrollArea className="flex-1 px-4 md:px-6">
      <div 
        className="py-4 space-y-4"
        role="log"
        aria-live="polite"
        aria-label="聊天记录"
      >
        {activeMessages.map((msg, index) => {
          const isLast = index === activeMessages.length - 1;
          return (
            <React.Fragment key={msg.id}>
              <MessageBubble
                message={msg}
                onCopy={handleCopy}
                onRegenerate={
                  isLast && msg.role === 'assistant'
                    ? handleRegenerate
                    : undefined
                }
                onRetry={msg.status === 'error' ? handleRetry : undefined}
                onFeedback={handleFeedback}
                onDelete={handleDeleteMessage}
                onSendMessage={onSendMessage}
                onEditMessage={handleEditMessage}
                onSwitchBranch={handleSwitchBranch}
                branchInfo={getBranchInfo(linkedMessages, msg.id)}
                isLatest={isLast}
                isTyping={isLast && isAiTyping}
              />
              {index === 0 && activeMessages.length <= 1 && onSendMessage && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300 fill-mode-both">
                  <CapabilityCards onSelect={onSendMessage} />
                </div>
              )}
            </React.Fragment>
          );
        })}

        {footerContent}

        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  );
});

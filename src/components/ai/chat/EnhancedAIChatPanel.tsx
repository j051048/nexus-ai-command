import { EntityProfileDialog } from '@/components/ai/EntityProfileDialog';
import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';
import {
  Zap,
  ThumbsUp,
  Lightbulb,
  Sparkles,
} from 'lucide-react';
import { ChatHeader } from './ChatHeader';
import { ChatMessageList } from './ChatMessageList';
import { ChatInputArea } from './ChatInputArea';
import { QuotaDisplay } from './QuotaDisplay';
import { ChatSuggestions } from './ChatSuggestions';
import { ChatHistorySidebar } from './ChatHistorySidebar';
import { useChatPanel } from './useChatPanel';
import { ProactiveCopilotPanel } from '@/components/ai/ProactiveCopilotPanel';

interface EnhancedAIChatPanelProps {
  isExpanded: boolean;
  onToggle: () => void;
  defaultAgent?: string;
  onSendMessage?: (message: string, response: string) => void;
  variant?: 'overlay' | 'embedded';
  compact?: boolean;
}

const agentTags = [
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
  const chat = useChatPanel({ isExpanded, onToggle, defaultAgent, onSendMessage, agentTags });

  const panelHeightClass = useMemo(() => {
    if (chat.isFullscreen) return 'h-[100dvh]';
    if (isExpanded) return 'h-[85dvh] md:h-[500px]';
    return 'h-16';
  }, [isExpanded, chat.isFullscreen]);

  return (
    <>
      {chat.isMobile && isExpanded && variant !== 'embedded' && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 animate-fade-in"
          onClick={onToggle}
        />
      )}

      <div
        className={cn(
          'bg-card border-border transition-all duration-300 shadow-xl flex flex-col',
          chat.isMobile && isExpanded && variant !== 'embedded' ? 'fixed inset-0 z-50 bg-background' : '',
          chat.isMobile && variant === 'embedded' ? 'relative h-full w-full bg-background' : '',
          !chat.isMobile && variant === 'overlay' ? 'fixed z-50 shadow-[0_-4px_20px_-1px_rgba(0,0,0,0.1)]' : '',
          !chat.isMobile && variant === 'embedded' ? 'relative h-full w-full border-r' : '',
          !chat.isMobile && variant === 'overlay' && chat.isFullscreen ? 'inset-0 rounded-none' : '',
          !chat.isMobile && variant === 'overlay' && !chat.isFullscreen ? 'bottom-0 left-0 right-0 md:left-64 md:right-80 rounded-t-2xl md:rounded-none' : '',
          variant === 'overlay' && !chat.isMobile ? panelHeightClass : 'h-full'
        )}
      >
        {!compact && (
          <>
            <ChatHeader
              isExpanded={isExpanded}
              onToggle={onToggle}
              variant={variant}
              isAiTyping={chat.isAiTyping}
              aiStatus={chat.aiStatus}
              isFullscreen={chat.isFullscreen}
              setIsFullscreen={chat.setIsFullscreen}
              isMobile={chat.isMobile}
              showTrace={chat.showTrace}
              setShowTrace={chat.setShowTrace}
              handleClearChat={chat.handleClearChat}
              onExportChat={chat.handleExportChat}
              onShowHistory={() => chat.setShowHistory(true)}
              aria-label="对话窗口顶部工具栏"
            />

            <ChatHistorySidebar
              currentSessionId={chat.sessionId}
              onSelectSession={chat.handleSelectSession}
              onNewChat={chat.handleNewChat}
              isOpen={chat.showHistory}
              onClose={() => chat.setShowHistory(false)}
            />
          </>
        )}

        {(isExpanded || variant === 'embedded') && (
          <div className={cn(
            'flex flex-col flex-1 min-h-0',
            variant === 'overlay' && chat.isFullscreen ? 'h-[calc(100dvh-4rem)]' : '',
              variant === 'overlay' && !chat.isFullscreen ? 'h-[calc(85dvh-4rem)] md:h-[436px]' : ''
          )}>
            {variant === 'embedded' && chat.messages.length === 0 && !chat.isAiTyping && (
              <ProactiveCopilotPanel onSendMessage={chat.handleSend} />
            )}

            <ChatMessageList
              messages={chat.messages}
              setMessages={chat.setMessages}
              isAiTyping={chat.isAiTyping}
              aiStatus={chat.aiStatus}
              userId={chat.user.id}
              handleCopy={chat.handleCopy}
              handleRegenerate={chat.handleRegenerate}
              handleRetry={chat.handleRetry}
              handleDeleteMessage={chat.handleDeleteMessage}
              handleEditMessage={chat.handleEditMessage}
              handleSwitchBranch={chat.handleSwitchBranch}
              pendingConfirmation={chat.pendingConfirmation}
              confirmAndResend={chat.confirmAndResend}
              dismissConfirmation={chat.dismissConfirmation}
              pendingQuestion={chat.pendingQuestion}
              answerQuestion={chat.answerQuestion}
              dismissQuestion={chat.dismissQuestion}
              circuitBreak={chat.circuitBreak}
              dismissCircuitBreak={chat.dismissCircuitBreak}
              showTrace={chat.showTrace}
              setShowTrace={chat.setShowTrace}
              trace={chat.trace}
              orchestration={chat.orchestration}
              messagesEndRef={chat.messagesEndRef}
              onSendMessage={chat.handleSend}
            />

            {!chat.showAgents && (
              <ChatSuggestions
                showQuickReplies={chat.showQuickReplies}
                messagesCount={chat.messages.length}
                onQuickReply={chat.handleQuickReply}
                followUpSuggestions={chat.followUpSuggestions}
              />
            )}

            <QuotaDisplay quotaInfo={chat.quotaInfo} />

            <ChatInputArea
              input={chat.input}
              setInput={chat.setInput}
              handleSend={chat.handleSend}
              isAiTyping={chat.isAiTyping}
              stopStream={chat.stopStream}
              currentAgent={chat.currentAgent}
              setCurrentAgent={chat.setCurrentAgent}
              showAgents={chat.showAgents}
              setShowAgents={chat.setShowAgents}
              agentTags={agentTags}
              insertAgent={chat.insertAgent}
              isMobile={chat.isMobile}
              voiceMode={chat.voiceMode}
              setVoiceMode={chat.setVoiceMode}
              isRecording={chat.isRecording}
              isTranscribing={chat.isTranscribing}
              toggleRecording={chat.toggleRecording}
              showMobileMenu={chat.showMobileMenu}
              setShowMobileMenu={chat.setShowMobileMenu}
              inputRef={chat.inputRef}
              fileInputRef={chat.fileInputRef}
              handleFileUpload={chat.handleFileUpload}
              variant={variant}
              quotaAlert={chat.quotaAlert}
              setQuotaAlert={chat.setQuotaAlert}
              showToolPalette={chat.showToolPalette}
              setShowToolPalette={chat.setShowToolPalette}
              onSelectTool={chat.handleSelectTool}
              tools={chat.toolMetadata}
              toolsLoading={chat.toolsLoading}
              onSavePrompt={chat.handleSavePrompt}
              imageInputRef={chat.imageInputRef}
              handleImageUpload={chat.handleImageUpload}
              pendingImages={chat.pendingImages}
              removePendingImage={chat.removePendingImage}
            />
          </div>
        )}
      </div>
      <EntityProfileDialog
        entity={chat.entityDialogEntity}
        open={!!chat.entityDialogEntity}
        onOpenChange={(open) => { if (!open) chat.setEntityDialogEntity(null); }}
      />
    </>
  );
}

export default EnhancedAIChatPanel;

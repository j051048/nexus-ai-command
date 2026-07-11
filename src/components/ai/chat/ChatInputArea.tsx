import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import {
  Send,
  AtSign,
  Mic,
  Loader2,
  X,
  Square,
  ImagePlus,
} from 'lucide-react';
import { ToolPalette } from './ToolPalette';

interface AgentTag {
  id: string;
  name: string;
  color: string;
  description: string;
  icon: React.ReactNode;
}

interface QuotaAlert {
  alert_level: 'normal' | 'warning' | 'critical' | 'exhausted';
  usage_percentage: number;
  alert_message: string | null;
}

interface ChatInputAreaProps {
  input: string;
  setInput: (v: string) => void;
  handleSend: () => void;
  isAiTyping: boolean;
  stopStream: () => void;
  currentAgent: string | undefined;
  setCurrentAgent: (v: string | undefined) => void;
  showAgents: boolean;
  setShowAgents: (v: boolean) => void;
  agentTags: AgentTag[];
  insertAgent: (agent: AgentTag) => void;
  isMobile: boolean;
  voiceMode: boolean;
  setVoiceMode: (v: boolean) => void;
  isRecording: boolean;
  isTranscribing: boolean;
  toggleRecording: () => void;
  showMobileMenu: boolean;
  setShowMobileMenu: (v: React.SetStateAction<boolean>) => void;
  inputRef: React.RefObject<HTMLTextAreaElement>;
  fileInputRef: React.RefObject<HTMLInputElement>;
  handleFileUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  variant: 'overlay' | 'embedded';
  quotaAlert: QuotaAlert | null;
  setQuotaAlert: (v: QuotaAlert | null) => void;
  showToolPalette?: boolean;
  setShowToolPalette?: (v: boolean) => void;
  onSelectTool?: (tool: { name: string; description: string; domain: string | null }) => void;
  tools?: { name: string; description: string; domain: string | null }[];
  toolsLoading?: boolean;
  onSavePrompt?: (prompt: string) => void;
  imageInputRef?: React.RefObject<HTMLInputElement>;
  handleImageUpload?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  pendingImages?: Array<{ file: File; previewUrl: string; uploadedUrl?: string }>;
  removePendingImage?: (previewUrl: string) => void;
}

const INPUT_HINTS: { prefix: string; hint: string }[] = [
  { prefix: '查看', hint: '查看本周销售汇总' },
  { prefix: '分析', hint: '分析商机转化率' },
  { prefix: '帮我', hint: '帮我写一封跟进邮件' },
  { prefix: '对比', hint: '对比上月和本月业绩' },
  { prefix: '生成', hint: '生成客户拜访报告' },
  { prefix: '统计', hint: '统计本月新增客户数' },
];

export const ChatInputArea = React.memo(function ChatInputArea({
  input,
  setInput,
  handleSend,
  isAiTyping,
  stopStream,
  currentAgent,
  setCurrentAgent,
  showAgents,
  setShowAgents,
  agentTags,
  insertAgent,
  isMobile,
  isRecording,
  toggleRecording,
  inputRef,
  variant,
  quotaAlert,
  setQuotaAlert,
  showToolPalette,
  setShowToolPalette,
  onSelectTool,
  tools,
  toolsLoading,
  imageInputRef,
  handleImageUpload,
  pendingImages,
}: ChatInputAreaProps) {
  const matchedHint = useMemo(() => {
    if (!input || input.length > 10) return null;
    const trimmed = input.trim();
    if (!trimmed) return null;
    const match = INPUT_HINTS.find(h => h.hint.startsWith(trimmed) && h.hint !== trimmed);
    return match?.hint || null;
  }, [input]);

  return (
    <>

      <div className={cn(
        "sticky bottom-0 z-20 border-t bg-card px-3 py-3 md:px-4",
        variant === 'embedded' ? 'pb-3' : 'pb-[calc(0.75rem+env(safe-area-inset-bottom))]'
      )}>
        <div className="relative mx-auto max-w-4xl rounded-lg border bg-background p-2 shadow-sm">
          
          {showAgents && (
            <div className="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-lg border bg-popover p-3 shadow-lg">
              <div className="flex items-center justify-between mb-4 px-2 relative z-10">
                <p className="text-xs font-medium text-foreground">选择业务助手</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 relative z-10">
                {agentTags.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => insertAgent(agent)}
                    className={cn(
                      'group/agent flex items-center gap-3 rounded-md border p-3 text-left transition-colors',
                      'bg-background hover:bg-muted/40',
                      agent.color.split(' ')[0] // extraction only text color for the title
                    )}
                  >
                    <div className="rounded-md border bg-muted/30 p-2">
                      {agent.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-bold text-foreground group-hover/agent:text-primary transition-colors">{agent.name}</p>
                      <p className="text-micro text-muted-foreground/60 line-clamp-1 group-hover/agent:text-muted-foreground/90">{agent.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 relative z-10">
            <div className="hidden md:flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 text-muted-foreground hover:text-primary"
                onClick={() => setShowAgents(!showAgents)}
              >
                <AtSign className={cn("w-5 h-5", showAgents && "text-primary")} />
              </Button>

              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 text-muted-foreground hover:text-success"
                onClick={() => imageInputRef?.current?.click()}
              >
                <ImagePlus className="w-5 h-5" />
              </Button>
            </div>

            <div className="flex-1 relative flex items-center min-w-0">
              <textarea
                data-testid="chat-input"
                ref={inputRef}
                value={input}
                rows={1}
                onChange={(e) => {
                  const val = e.target.value;
                  setInput(val);
                  // Auto-grow: reset height then set to scrollHeight (max 5 rows ~120px)
                  e.target.style.height = 'auto';
                  e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                  if (val.endsWith('@') && !showAgents) setShowAgents(true);
                  if (val.endsWith('/') && !showToolPalette && setShowToolPalette) setShowToolPalette(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Tab' && matchedHint) {
                    e.preventDefault();
                    setInput(matchedHint);
                  } else if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                  // Shift+Enter inserts newline (default textarea behavior)
                }}
                placeholder={currentAgent ? `对话专家: ${currentAgent}` : "输入指令并回车 / 或输入 @ 召唤专家..."}
                className="w-full resize-none overflow-y-auto rounded-md bg-transparent px-3 py-2.5 text-sm leading-normal placeholder:text-muted-foreground/60 focus:outline-none"
                style={{ maxHeight: '120px' }}
              />
            </div>

            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className={cn("h-9 w-9 text-muted-foreground", isRecording && "bg-destructive/10 text-destructive")}
                onClick={toggleRecording}
              >
                {isRecording ? <Square className="w-4 h-4" /> : <Mic className="w-5 h-5" />}
              </Button>

              {isAiTyping ? (
                <Button size="icon" className="h-9 w-9 bg-destructive text-destructive-foreground" onClick={stopStream}>
                  <Square className="w-4 h-4" />
                </Button>
              ) : (
                <Button
                  size="icon"
                  className={cn("h-9 w-9", input.trim() ? "bg-primary opacity-100" : "bg-muted opacity-50")}
                  onClick={handleSend}
                  disabled={!input.trim()}
                >
                  <Send className="w-5 h-5" />
                </Button>
              )}
            </div>
          </div>
        </div>
        <p className="mt-2 hidden text-center text-[10px] text-muted-foreground/60 md:block">
          SHIFT + ENTER 换行 · @ 专家模式 · / 工作流
        </p>
      </div>

      <input
        type="file"
        ref={imageInputRef}
        className="hidden"
        onChange={handleImageUpload}
        accept="image/*"
        multiple
      />
    </>
  );
});

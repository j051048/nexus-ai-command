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
  inputRef: React.RefObject<HTMLInputElement>;
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
      {quotaAlert && (
        <div className={cn(
          'mx-4 md:mx-6 mb-1 px-3 py-2 rounded-lg text-xs flex items-center gap-2',
          quotaAlert.alert_level === 'exhausted' && 'bg-destructive/10 text-destructive border border-destructive/20',
          quotaAlert.alert_level === 'critical' && 'bg-orange-500/10 text-orange-600 border border-orange-500/20',
        )}>
          <AtSign className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="flex-1">{quotaAlert.alert_message}</span>
          <button onClick={() => setQuotaAlert(null)}><X className="w-3 h-3" /></button>
        </div>
      )}

      <div className={cn(
        "px-4 md:px-8 py-6 sticky bottom-0 z-20",
        variant === 'embedded' ? 'pb-6' : 'pb-[calc(1.5rem+env(safe-area-inset-bottom))]'
      )}>
        <div className="max-w-4xl mx-auto command-capsule glass-premium border-white/10 shadow-2xl p-2 md:p-3 relative group/capsule">
          <div className="absolute inset-x-12 -top-px h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent opacity-0 group-hover/capsule:opacity-100 transition-opacity" />
          
          {showAgents && (
            <div className="absolute bottom-full left-0 right-0 mb-4 p-4 glass-premium border-white/20 rounded-3xl animate-in fade-in slide-in-from-bottom-4 shadow-[0_20px_50px_rgba(0,0,0,0.3)] backdrop-blur-2xl overflow-hidden z-50">
              <div className="absolute inset-0 bg-gradient-to-b from-white/5 to-transparent pointer-events-none" />
              <div className="flex items-center justify-between mb-4 px-2 relative z-10">
                <p className="text-[10px] font-bold text-primary/80 uppercase tracking-[0.2em]">智能专家集群</p>
                <div className="h-1 w-8 rounded-full bg-primary/20" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 relative z-10">
                {agentTags.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => insertAgent(agent)}
                    className={cn(
                      'group/agent flex items-center gap-4 p-3 rounded-2xl text-left transition-all duration-300',
                      'bg-white/5 border border-white/5 hover:bg-primary/10 hover:border-primary/20 hover:translate-y-[-2px] hover:shadow-lg',
                      agent.color.split(' ')[0] // extraction only text color for the title
                    )}
                  >
                    <div className="p-3 rounded-xl bg-white/5 shadow-inner group-hover/agent:scale-110 transition-transform">
                      {agent.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-bold text-foreground group-hover/agent:text-primary transition-colors">{agent.name}</p>
                      <p className="text-[10px] text-muted-foreground/60 line-clamp-1 group-hover/agent:text-muted-foreground/90">{agent.description}</p>
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
                className="h-10 w-10 text-muted-foreground/60 hover:text-primary hover:bg-white/5 transition-all rounded-xl"
                onClick={() => setShowAgents(!showAgents)}
              >
                <AtSign className={cn("w-5 h-5", showAgents && "text-primary")} />
              </Button>

              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10 text-muted-foreground/60 hover:text-green-500 hover:bg-white/5 transition-all rounded-xl"
                onClick={() => imageInputRef?.current?.click()}
              >
                <ImagePlus className="w-5 h-5" />
              </Button>
            </div>

            <div className="flex-1 relative flex items-center min-w-0">
              {currentAgent && (
                <div className="absolute left-2 inset-y-2 z-10">
                  <Badge variant="secondary" className="h-full px-2 gap-1 bg-primary/20 text-primary-foreground border-none text-[10px] font-bold">
                    @{currentAgent}
                    <X className="w-3 h-3 cursor-pointer" onClick={() => setCurrentAgent(undefined)} />
                  </Badge>
                </div>
              )}
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => {
                  const val = e.target.value;
                  setInput(val);
                  if (val.endsWith('@') && !showAgents) setShowAgents(true);
                  if (val.endsWith('/') && !showToolPalette && setShowToolPalette) setShowToolPalette(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Tab' && matchedHint) {
                    e.preventDefault();
                    setInput(matchedHint);
                  } else if (e.key === 'Enter' && !e.shiftKey) {
                    handleSend();
                  }
                }}
                placeholder={currentAgent ? "" : "输入指令并回车 / 或输入 @ 召唤专家..."}
                className={cn(
                  "w-full bg-black/20 dark:bg-white/5 rounded-xl py-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30 transition-all placeholder:text-muted-foreground/40",
                  currentAgent ? "pl-20 pr-4" : "px-4"
                )}
              />
            </div>

            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className={cn("h-10 w-10 text-muted-foreground hover:bg-white/5 rounded-xl transition-all", isRecording && "bg-red-500/20 text-red-500 animate-pulse")}
                onClick={toggleRecording}
              >
                {isRecording ? <Square className="w-4 h-4" /> : <Mic className="w-5 h-5" />}
              </Button>

              {isAiTyping ? (
                <Button size="icon" className="h-10 w-10 bg-red-600 hover:bg-red-700 text-white rounded-xl shadow-lg animate-pulse" onClick={stopStream}>
                  <Square className="w-4 h-4" />
                </Button>
              ) : (
                <Button
                  size="icon"
                  className={cn("h-10 w-10 rounded-xl transition-all duration-500 shadow-xl", input.trim() ? "bg-primary scale-100 opacity-100" : "bg-muted scale-95 opacity-50")}
                  onClick={handleSend}
                  disabled={!input.trim()}
                >
                  <Send className="w-5 h-5" />
                </Button>
              )}
            </div>
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground/40 mt-3 text-center font-mono uppercase hidden md:block">
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

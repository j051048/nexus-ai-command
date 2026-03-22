import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import {
  Send,
  Mic,
  MicOff,
  AtSign,
  Loader2,
  Paperclip,
  Plus,
  X,
  Keyboard,
  AlertTriangle,
  Square,
  Wrench,
  Bookmark,
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
  // P3: 图片上传（不进入RAG知识库）
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
  voiceMode,
  setVoiceMode,
  isRecording,
  isTranscribing,
  toggleRecording,
  showMobileMenu,
  setShowMobileMenu,
  inputRef,
  fileInputRef,
  handleFileUpload,
  variant,
  quotaAlert,
  setQuotaAlert,
  showToolPalette,
  setShowToolPalette,
  onSelectTool,
  tools,
  toolsLoading,
  onSavePrompt,
  imageInputRef,
  handleImageUpload,
  pendingImages,
  removePendingImage,
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
          quotaAlert.alert_level === 'warning' && 'bg-yellow-500/10 text-yellow-600 border border-yellow-500/20',
        )}>
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="flex-1">{quotaAlert.alert_message}</span>
          <button
            className="text-muted-foreground hover:text-foreground"
            onClick={() => setQuotaAlert(null)}
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}
      <div className={cn(
        "px-4 md:px-6 py-3 border-t border-border bg-card sticky bottom-0",
        variant === 'embedded' ? 'pb-3' : 'pb-[calc(1rem+env(safe-area-inset-bottom))]'
      )}>
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

        {showToolPalette && setShowToolPalette && onSelectTool && tools && (
          <ToolPalette
            tools={tools}
            isLoading={toolsLoading || false}
            onSelectTool={onSelectTool}
            onClose={() => setShowToolPalette(false)}
          />
        )}

        {showMobileMenu && (
          <div className="mb-3 p-2 bg-secondary/50 rounded-lg animate-fade-slide-up sm:hidden">
            <div className="grid grid-cols-4 gap-2">
              <button
                onClick={() => { setShowAgents(!showAgents); setShowMobileMenu(false); }}
                className="flex flex-col items-center gap-1 p-3 rounded-lg hover:bg-secondary active:bg-secondary transition-colors"
              >
                <AtSign className="w-5 h-5 text-blue-500" />
                <span className="text-xs text-muted-foreground">AI助手</span>
              </button>
              <button
                onClick={() => { fileInputRef.current?.click(); setShowMobileMenu(false); }}
                className="flex flex-col items-center gap-1 p-3 rounded-lg hover:bg-secondary active:bg-secondary transition-colors"
              >
                <Paperclip className="w-5 h-5 text-green-500" />
                <span className="text-xs text-muted-foreground">上传文档</span>
              </button>
              {imageInputRef && handleImageUpload && (
                <button
                  onClick={() => { imageInputRef.current?.click(); setShowMobileMenu(false); }}
                  className="flex flex-col items-center gap-1 p-3 rounded-lg hover:bg-secondary active:bg-secondary transition-colors"
                >
                  <ImagePlus className="w-5 h-5 text-purple-500" />
                  <span className="text-xs text-muted-foreground">上传图片</span>
                </button>
              )}
              <button
                onClick={() => { setVoiceMode(!voiceMode); setShowMobileMenu(false); }}
                className="flex flex-col items-center gap-1 p-3 rounded-lg hover:bg-secondary active:bg-secondary transition-colors"
              >
                <Mic className={cn("w-5 h-5", voiceMode ? "text-red-500" : "text-orange-500")} />
                <span className="text-xs text-muted-foreground">{voiceMode ? '文字模式' : '语音模式'}</span>
              </button>
            </div>
          </div>
        )}

        <div className="flex items-center gap-2">
          <div className="flex sm:hidden">
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 flex-shrink-0"
              onClick={() => setShowMobileMenu(prev => !prev)}
            >
              <Plus className={cn("w-5 h-5 transition-transform", showMobileMenu && "rotate-45")} />
            </Button>
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="h-10 w-10 flex-shrink-0 sm:hidden"
            onClick={() => setVoiceMode(!voiceMode)}
          >
            {voiceMode ? (
              <Keyboard className="w-5 h-5" />
            ) : (
              <Mic className="w-5 h-5" />
            )}
          </Button>

          <div className="hidden sm:flex items-center gap-2">
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

            {imageInputRef && handleImageUpload && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-10 w-10 flex-shrink-0"
                    onClick={() => imageInputRef.current?.click()}
                  >
                    <ImagePlus className="w-5 h-5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>上传图片（不入知识库）</TooltipContent>
              </Tooltip>
            )}

            {onSavePrompt && input.trim() && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-10 w-10 flex-shrink-0"
                    onClick={() => onSavePrompt(input.trim())}
                  >
                    <Bookmark className="w-5 h-5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>保存为快捷指令</TooltipContent>
              </Tooltip>
            )}
          </div>

          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            onChange={handleFileUpload}
            accept=".pdf,.txt,.md,.csv,.json,.docx"
          />
          {imageInputRef && handleImageUpload && (
            <input
              type="file"
              ref={imageInputRef}
              className="hidden"
              onChange={handleImageUpload}
              accept="image/jpeg,image/png,image/webp,image/gif"
              multiple
            />
          )}

          {pendingImages && pendingImages.length > 0 && removePendingImage && (
            <div className="flex gap-2 mb-2 flex-wrap">
              {pendingImages.map((img) => (
                <div key={img.previewUrl} className="relative w-16 h-16 rounded-lg overflow-hidden border border-border group">
                  <img src={img.previewUrl} alt={img.file.name} className="w-full h-full object-cover" />
                  {!img.uploadedUrl && (
                    <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                      <Loader2 className="w-4 h-4 text-white animate-spin" />
                    </div>
                  )}
                  <button
                    className="absolute top-0.5 right-0.5 w-4 h-4 bg-black/60 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => removePendingImage(img.previewUrl)}
                  >
                    <X className="w-3 h-3 text-white" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {voiceMode && isMobile ? (
            <button
              className={cn(
                "flex-1 h-12 rounded-xl text-sm font-medium select-none transition-all",
                "active:scale-[0.98]",
                isRecording
                  ? "bg-red-500/10 text-red-500 border-2 border-red-500/30 animate-pulse"
                  : "bg-secondary text-muted-foreground border-2 border-transparent",
                isTranscribing && "opacity-50 pointer-events-none"
              )}
              onClick={toggleRecording}
              disabled={isTranscribing || isAiTyping}
            >
              {isTranscribing ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  识别中...
                </span>
              ) : isRecording ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                  录音中... 点击结束
                </span>
              ) : (
                '点击开始说话'
              )}
            </button>
          ) : (
            <div className="flex-1 relative">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => {
                const val = e.target.value;
                setInput(val);
                // Auto-trigger agent picker when user types @
                if (val.endsWith('@') && !showAgents) {
                  setShowAgents(true);
                }
                // Auto-trigger tool palette when user types /
                if (val.endsWith('/') && !showToolPalette && setShowToolPalette) {
                  setShowToolPalette(true);
                }
              }}
                onKeyDown={(e) => {
                  if (e.key === 'Tab' && matchedHint) {
                    e.preventDefault();
                    setInput(matchedHint);
                  } else if (e.key === 'Enter' && !e.shiftKey) {
                    handleSend();
                  }
                }}
                placeholder={
                  currentAgent
                    ? `向 ${currentAgent} 提问...`
                    : '输入指令... 按 @ 选择助手'
                }
                className="w-full bg-secondary rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
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
              {matchedHint && (
                <div className="absolute inset-0 pointer-events-none px-4 py-3 text-sm">
                  <span className="invisible">{input}</span>
                  <span className="text-muted-foreground/40">{matchedHint.slice(input.length)}</span>
                </div>
              )}
            </div>
          )}

          <div className="hidden sm:block">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={isRecording ? 'destructive' : 'ghost'}
                  size="icon"
                  className={cn(
                    'h-10 w-10 flex-shrink-0 relative',
                    isRecording && 'animate-pulse'
                  )}
                  onClick={toggleRecording}
                >
                  {isRecording && (
                    <span className="absolute inset-0 rounded-md bg-red-500/20 animate-ping" />
                  )}
                  {isRecording ? (
                    <MicOff className="w-5 h-5 relative z-10" />
                  ) : (
                    <Mic className="w-5 h-5" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {isRecording ? '停止录音' : '语音输入'}
              </TooltipContent>
            </Tooltip>
          </div>

          {!(voiceMode && isMobile) && (
          <>
          {isAiTyping ? (
            <Button
              size="icon"
              variant="destructive"
              className="h-10 w-10 flex-shrink-0 shadow-lg animate-pulse"
              onClick={stopStream}
              title="停止生成"
            >
              <Square className="w-4 h-4" />
            </Button>
          ) : (
          <Button
            size="icon"
            className={cn(
              'h-10 w-10 flex-shrink-0 transition-all',
              input.trim()
                ? 'bg-primary hover:bg-primary/90 shadow-lg'
                : 'bg-secondary text-muted-foreground'
            )}
            onClick={handleSend}
            disabled={!input.trim() && !(pendingImages && pendingImages.some(img => img.uploadedUrl))}
          >
            <Send className="w-5 h-5" />
          </Button>
          )}
          </>
          )}
        </div>

        <p className="text-[10px] text-muted-foreground mt-2 text-center hidden md:block">
          按 <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Enter</kbd> 发送
          {' · '}
          <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">@</kbd> 选择助手
          {' · '}
          <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">/</kbd> 工具面板
          {' · '}
          <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Tab</kbd> 补全
          {' · '}
          <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">⌘K</kbd> 命令面板
          {isAiTyping && (
            <>
              {' · '}
              <button className="text-destructive hover:underline" onClick={stopStream}>停止生成</button>
            </>
          )}
        </p>
      </div>
    </>
  );
});

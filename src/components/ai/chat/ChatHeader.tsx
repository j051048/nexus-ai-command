import React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Bot,
  ChevronUp,
  ChevronDown,
  Sparkles,
  Loader2,
  Maximize2,
  Minimize2,
  PanelLeftClose,
  PanelLeftOpen,
  X,
  History,
  Settings,
  Zap,
  Trash2,
  Download,
} from 'lucide-react';
import { PulseDot } from '@/components/common/AnimatedComponents';

interface ChatHeaderProps {
  isExpanded: boolean;
  onToggle: () => void;
  variant: 'overlay' | 'embedded';
  isAiTyping: boolean;
  aiStatus: string | undefined;
  isFullscreen: boolean;
  setIsFullscreen: (v: boolean) => void;
  isMobile: boolean;
  showTrace: boolean;
  setShowTrace: (v: boolean) => void;
  handleClearChat: () => void;
}

export function ChatHeader({
  isExpanded,
  onToggle,
  variant,
  isAiTyping,
  aiStatus,
  isFullscreen,
  setIsFullscreen,
  isMobile,
  showTrace,
  setShowTrace,
  handleClearChat,
}: ChatHeaderProps) {
  return (
    <div
      className={cn(
        'h-16 px-4 md:px-6 flex items-center justify-between cursor-pointer hover:bg-card-elevated/50 transition-colors',
        isFullscreen || isMobile ? 'rounded-none' : 'rounded-t-2xl md:rounded-t-none'
      )}
      onClick={(!isFullscreen && !isMobile) ? onToggle : undefined}
    >
      <div className="flex items-center gap-3">
        <div className="relative">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-lg">
            <Bot className="w-5 h-5 text-primary-foreground" />
          </div>
          {isAiTyping && (
            <span className="absolute -bottom-0.5 -right-0.5">
              <PulseDot color="success" size="sm" />
            </span>
          )}
        </div>
        <div>
          <h3 className="font-semibold text-foreground flex items-center gap-2">
            AI 指挥中心
            <Sparkles className="w-4 h-4 text-primary" />
          </h3>
          <div className="text-xs text-muted-foreground flex items-center gap-2">
              <div className="flex items-center gap-2">
                {aiStatus ? (
                  <div className="flex items-center gap-1.5 bg-secondary/80 px-2 py-0.5 rounded-full animate-pulse">
                     <Loader2 className="w-3 h-3 animate-spin text-primary" />
                     <span className="text-primary font-medium">{aiStatus}</span>
                  </div>
                ) : isAiTyping ? (
                  <span className="text-muted-foreground">AI正在思考...</span>
                ) : (
                  '输入指令或 @ 选择专属助手'
                )}
              </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1">
        {isMobile && isExpanded ? (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            data-compact
            onClick={onToggle}
          >
            <X className="w-4 h-4" />
          </Button>
        ) : (
          <>
            {variant === 'overlay' && isExpanded && (
              <>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant={showTrace ? 'default' : 'ghost'}
                      size="icon"
                      className="h-8 w-8"
                      data-compact
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowTrace(!showTrace);
                      }}
                    >
                      <Zap className="w-4 h-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {showTrace ? '隐藏执行日志' : '查看执行日志'}
                  </TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      data-compact
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsFullscreen(!isFullscreen);
                      }}
                    >
                      {isFullscreen ? (
                        <Minimize2 className="w-4 h-4" />
                      ) : (
                        <Maximize2 className="w-4 h-4" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {isFullscreen ? '退出全屏' : '全屏模式'}
                  </TooltipContent>
                </Tooltip>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      data-compact
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Settings className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={handleClearChat}>
                      <Trash2 className="w-4 h-4 mr-2" />
                      清空对话
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Download className="w-4 h-4 mr-2" />
                      导出对话
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem>
                      <History className="w-4 h-4 mr-2" />
                      历史记录
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </>
            )}

            {isFullscreen ? (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                data-compact
                onClick={() => {
                  setIsFullscreen(false);
                  onToggle();
                }}
              >
                <X className="w-4 h-4" />
              </Button>
            ) : (
              <button
                className="p-2 rounded-lg hover:bg-secondary transition-colors"
                onClick={(e) => {
                  if (variant === 'embedded') {
                    e.stopPropagation();
                    onToggle();
                  }
                }}
              >
                {variant === 'embedded' ? (
                  isExpanded ? <PanelLeftClose className="w-5 h-5 text-muted-foreground hover:text-foreground" /> : <PanelLeftOpen className="w-5 h-5" />
                ) : (
                  isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronUp className="w-5 h-5" />
                )}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

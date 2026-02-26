import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Bot, Copy, RotateCcw, ThumbsUp, ThumbsDown, User, Check, MoreHorizontal, Trash2, Download } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import { AIMessage } from '@/types/nexus';
import { getEnterAnimationClass } from '@/lib/animations';
import { GenUIContainer } from './GenUIContainer';

interface MessageBubbleProps {
  message: AIMessage;
  onCopy: (content: string) => void;
  onRegenerate?: () => void;
  onFeedback?: (type: 'positive' | 'negative') => void;
  onDelete?: () => void;
  isLatest?: boolean;
  isTyping?: boolean;
}

export const MessageBubble = React.memo(function MessageBubble({
  message,
  onCopy,
  onRegenerate,
  onFeedback,
  onDelete,
  isLatest,
  isTyping,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    onCopy(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedback = (type: 'positive' | 'negative') => {
    setFeedback(type);
    onFeedback?.(type);
    toast.success(type === 'positive' ? '感谢您的反馈！' : '我们会继续改进');
  };

  return (
    <div
      className={cn(
        'group flex gap-3 transition-all mb-4',
        isUser ? 'justify-end' : 'justify-start',
        getEnterAnimationClass('fade', 'fast')
      )}
    >
      {!isUser && (
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center flex-shrink-0 shadow-sm mt-1">
          <Bot className="w-4 h-4 text-primary-foreground" />
        </div>
      )}

      <div className={cn('flex flex-col max-w-[85%] md:max-w-2xl', isUser && 'items-end')}>
        {!isUser && message.agent && (
          <div className="flex items-center gap-2 mb-1 pl-1">
            <span className="text-xs font-medium text-foreground">{message.agent}</span>
            <span className="text-[10px] text-muted-foreground">
              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        )}

        {isUser && (
           <div className="flex items-center gap-2 mb-1 pr-1">
             <span className="text-[10px] text-muted-foreground">
               {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
             </span>
             <span className="text-xs font-medium text-foreground">You</span>
           </div>
        )}

        <div
          className={cn(
            'rounded-2xl px-4 py-3 shadow-sm relative overflow-hidden',
            isUser
              ? 'bg-primary text-primary-foreground rounded-br-sm'
              : 'bg-card border border-border text-card-foreground rounded-bl-sm'
          )}
        >
          {isTyping && isLatest && !message.content ? (
            <div className="flex items-center gap-1.5 h-6">
              <span className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-current rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          ) : (
            <div className={cn("prose prose-sm max-w-none dark:prose-invert break-words", isUser && "text-primary-foreground prose-headings:text-primary-foreground prose-a:text-primary-foreground prose-strong:text-primary-foreground prose-code:text-primary-foreground/90")}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  code({ node, inline, className, children, ...props }: React.ClassAttributes<HTMLElement> & React.HTMLAttributes<HTMLElement> & { inline?: boolean, node?: any }) {
                    const match = /language-(\w+[-]?\w*)/.exec(className || '');
                    const lang = match?.[1]?.toLowerCase() || '';
                    const raw = String(children).trim();

                    // P0: Generative UI Support — multi-layer detection
                    // Layer 1: Match explicit GenUI language tags (gen-ui, gen, genui, gen_ui)
                    const isGenUITag = ['gen-ui', 'gen', 'genui', 'gen_ui'].includes(lang);
                    // Layer 2: Detect GenUI JSON structure in any code block
                    // Matches {"component":"...", "props": ...} pattern even with json/no tag
                    const isGenUIContent = !inline && !isGenUITag && raw.startsWith('{') &&
                      /^\s*\{\s*"component"\s*:/.test(raw);

                    if (isGenUITag || isGenUIContent) {
                      try {
                        const config = JSON.parse(raw);
                        if (config.component && typeof config.component === 'string') {
                          return <GenUIContainer componentName={config.component} props={config.props || {}} />;
                        }
                      } catch {
                        // During streaming, JSON may be incomplete — show skeleton instead of error
                        if (isTyping) {
                          return (
                            <div className="my-4 w-full rounded-xl border border-border bg-card p-6 space-y-3 animate-pulse">
                              <div className="flex items-center gap-2">
                                <div className="h-4 w-4 rounded bg-primary/20" />
                                <div className="h-4 w-24 rounded bg-muted" />
                              </div>
                              <div className="h-32 w-full rounded bg-muted/50" />
                            </div>
                          );
                        }
                        // If tag was explicitly GenUI but JSON is invalid, show friendly error
                        if (isGenUITag) {
                          console.error("GenUI Parse Error:", raw);
                          return (
                            <div className="my-4 w-full rounded-xl border border-amber-500/30 bg-amber-50 dark:bg-amber-950/20 p-4 text-sm text-amber-700 dark:text-amber-400">
                              组件加载失败，正在以文本形式展示...
                            </div>
                          );
                        }
                        // For content-detected blocks, fall through to normal code rendering
                      }
                    }

                    return !inline && match ? (
                      <div className="relative rounded-md overflow-hidden my-2">
                         <div className="flex items-center justify-between px-3 py-1 bg-zinc-900 border-b border-zinc-700">
                            <span className="text-xs text-zinc-400">{match[1]}</span>
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(String(children));
                                toast.success("代码已复制");
                              }}
                              className="text-xs text-zinc-400 hover:text-white"
                            >
                                <Copy className="w-3 h-3" />
                            </button>
                         </div>
                        <SyntaxHighlighter
                          style={vscDarkPlus}
                          language={match[1]}
                          PreTag="div"
                          customStyle={{ margin: 0, borderRadius: '0 0 0.375rem 0.375rem' }}
                          {...props}
                        >
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                      </div>
                    ) : (
                      <code className={cn("bg-muted/50 px-1 py-0.5 rounded font-mono text-sm", className)} {...props}>
                        {children}
                      </code>
                    );
                  },
                  a: ({ node, ...props }) => (
                     <a target="_blank" rel="noopener noreferrer" className="underline decoration-dotted underline-offset-4 hover:decoration-solid" {...props} />
                  ),
                  table: ({ node, ...props }) => (
                     <div className="overflow-x-auto my-4 border rounded-md">
                        <table className="w-full text-sm text-left" {...props} />
                     </div>
                  ),
                  th: ({ node, ...props }) => (
                     <th className="border-b bg-muted/50 px-4 py-2 font-medium" {...props} />
                  ),
                  td: ({ node, ...props }) => (
                     <td className="border-b px-4 py-2" {...props} />
                  ),
                  blockquote: ({ node, ...props }) => (
                    <blockquote className="border-l-4 border-primary/30 pl-4 py-1 my-2 italic bg-muted/20 rounded-r" {...props} />
                  )
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Action Bar for Assistant Messages */}
        {!isUser && message.content && (
          <div className={cn(
            'flex items-center gap-1 mt-1.5 transition-opacity',
            'opacity-0 group-hover:opacity-100'
          )}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0"
                  data-compact
                  onClick={handleCopy}
                >
                  {copied ? (
                    <Check className="w-3.5 h-3.5 text-green-500" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">复制</TooltipContent>
            </Tooltip>

            {isLatest && onRegenerate && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0"
                    data-compact
                    onClick={onRegenerate}
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">重新生成</TooltipContent>
              </Tooltip>
            )}

            <div className="flex items-center gap-0.5 ml-1 border-l pl-1 border-border/50">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className={cn(
                      'h-6 w-6 p-0',
                      feedback === 'positive' && 'text-green-500'
                    )}
                    data-compact
                    onClick={() => handleFeedback('positive')}
                    disabled={feedback !== null}
                  >
                    <ThumbsUp className="w-3.5 h-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">有帮助</TooltipContent>
              </Tooltip>

              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className={cn(
                      'h-6 w-6 p-0',
                      feedback === 'negative' && 'text-red-500'
                    )}
                    data-compact
                    onClick={() => handleFeedback('negative')}
                    disabled={feedback !== null}
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">需改进</TooltipContent>
              </Tooltip>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 ml-auto" data-compact>
                  <MoreHorizontal className="w-3.5 h-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleCopy}>
                  <Copy className="w-4 h-4 mr-2" />
                  复制内容
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => {
                  const blob = new Blob([message.content], { type: 'text/plain' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'ai-response.txt';
                  a.click();
                }}>
                  <Download className="w-4 h-4 mr-2" />
                  导出文本
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={onDelete}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  删除消息
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
      </div>
      
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0 mt-1 border border-border">
            <User className="w-4 h-4 text-muted-foreground" />
        </div>
      )}
    </div>
  );
});

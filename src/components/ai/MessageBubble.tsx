import React, { useState, useMemo, lazy, Suspense } from 'react';
import { lazyWithRetry } from '@/lib/lazyPreload';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { StreamingMarkdown } from './StreamingMarkdown';
import { Bot, Copy, RotateCcw, ThumbsUp, ThumbsDown, User, Check, MoreHorizontal, Trash2, Download, AlertCircle, RefreshCw, Pencil, ChevronLeft, ChevronRight, ChevronDown, ChevronUp } from 'lucide-react';

interface SyntaxProps {
  children?: React.ReactNode;
  language?: string;
  style?: Record<string, React.CSSProperties>;
  PreTag?: string;
  customStyle?: React.CSSProperties;
  [key: string]: unknown;
}

// Lazy-load react-syntax-highlighter (~608KB) — only loaded when code blocks appear
const SyntaxHighlighter = lazyWithRetry(async () => {
  const [
    highlighter,
    javascript,
    typescript,
    python,
    bash,
    json,
    sql,
    css,
    markup,
  ] = await Promise.all([
    import('react-syntax-highlighter/dist/esm/prism-light'),
    import('react-syntax-highlighter/dist/esm/languages/prism/javascript'),
    import('react-syntax-highlighter/dist/esm/languages/prism/typescript'),
    import('react-syntax-highlighter/dist/esm/languages/prism/python'),
    import('react-syntax-highlighter/dist/esm/languages/prism/bash'),
    import('react-syntax-highlighter/dist/esm/languages/prism/json'),
    import('react-syntax-highlighter/dist/esm/languages/prism/sql'),
    import('react-syntax-highlighter/dist/esm/languages/prism/css'),
    import('react-syntax-highlighter/dist/esm/languages/prism/markup'),
  ]);

  highlighter.default.registerLanguage('javascript', javascript.default);
  highlighter.default.registerLanguage('js', javascript.default);
  highlighter.default.registerLanguage('typescript', typescript.default);
  highlighter.default.registerLanguage('ts', typescript.default);
  highlighter.default.registerLanguage('python', python.default);
  highlighter.default.registerLanguage('py', python.default);
  highlighter.default.registerLanguage('bash', bash.default);
  highlighter.default.registerLanguage('sh', bash.default);
  highlighter.default.registerLanguage('json', json.default);
  highlighter.default.registerLanguage('sql', sql.default);
  highlighter.default.registerLanguage('css', css.default);
  highlighter.default.registerLanguage('html', markup.default);
  highlighter.default.registerLanguage('xml', markup.default);

  return {
    default: highlighter.default as unknown as React.ComponentType<SyntaxProps>,
  };
}) as React.ComponentType<SyntaxProps>;
const loadStyle = () => import('react-syntax-highlighter/dist/esm/styles/prism/vsc-dark-plus').then(mod => mod.default);

// Wrapper that lazy-loads both the highlighter component and its style
function LazyCodeBlock({ language, children, ...props }: { language: string; children: string; [key: string]: unknown }) {
  const [style, setStyle] = React.useState<Record<string, React.CSSProperties> | null>(null);
  React.useEffect(() => { loadStyle().then(setStyle); }, []);
  return (
    <Suspense fallback={<pre className="bg-zinc-900 text-zinc-300 p-3 rounded-md text-sm overflow-x-auto"><code>{children}</code></pre>}>
      <SyntaxHighlighter
        language={language}
        style={style || {}}
        PreTag="div"
        customStyle={{ margin: 0, borderRadius: '0 0 0.375rem 0.375rem' }}
        {...props}
      >
        {children}
      </SyntaxHighlighter>
    </Suspense>
  );
}
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
import { InlineActions } from './genui/InlineActions';
import { ExecutionPulse } from './ExecutionPulse';

// ---------------------------------------------------------------------------
// Layer 3: Infer GenUI component name from props structure
// When LLM outputs just the props JSON without {"component": "...", "props": ...}
// wrapper, we try to match known prop signatures to auto-detect the component.
// ---------------------------------------------------------------------------
function inferGenUIComponent(obj: Record<string, unknown>): { component: string; confidence: number } | null {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return null;
  // EmailDraft: must have to + subject + body
  if (obj.to && obj.subject && obj.body) return { component: 'EmailDraft', confidence: 0.95 };
  // ReportCard: must have title + sections array
  if (obj.title && Array.isArray(obj.sections) && obj.sections.length > 0 &&
      obj.sections[0].heading && Array.isArray(obj.sections[0].items)) return { component: 'ReportCard', confidence: 0.9 };
  // StatCards: cards array with label+value
  if (Array.isArray(obj.cards) && obj.cards.length > 0 && obj.cards[0].label != null) return { component: 'StatCards', confidence: 0.9 };
  // DataTable: columns + rows arrays
  if (Array.isArray(obj.columns) && Array.isArray(obj.rows)) return { component: 'DataTable', confidence: 0.85 };
  // TodoList: items array with label field
  if (Array.isArray(obj.items) && obj.items.length > 0 && obj.items[0].label != null && obj.items[0].done !== undefined) return { component: 'TodoList', confidence: 0.85 };
  // AlertList: alerts array
  if (Array.isArray(obj.alerts) && obj.alerts.length > 0 && obj.alerts[0].level) return { component: 'AlertList', confidence: 0.85 };
  // Timeline: items with time+title+status
  if (Array.isArray(obj.items) && obj.items.length > 0 && obj.items[0].time && obj.items[0].title) return { component: 'Timeline', confidence: 0.8 };
  // ApprovalFlow: steps array with status
  if (Array.isArray(obj.steps) && obj.steps.length > 0 && obj.steps[0].status) return { component: 'ApprovalFlow', confidence: 0.8 };
  // FunnelChart: stages array
  if (Array.isArray(obj.stages) && obj.stages.length > 0 && obj.stages[0].value != null) return { component: 'FunnelChart', confidence: 0.8 };
  // PieChart: data array with label+value
  if (Array.isArray(obj.data) && obj.data.length > 0 && obj.data[0].label && obj.data[0].value != null) return { component: 'PieChart', confidence: 0.75 };
  // DataChart: data + dataKeys
  if (Array.isArray(obj.data) && Array.isArray(obj.dataKeys)) return { component: 'DataChart', confidence: 0.8 };
  // Dashboard: charts array with data+dataKeys — lower confidence due to generic structure
  if (Array.isArray(obj.charts) && obj.charts.length > 0 && Array.isArray(obj.charts[0].data)) return { component: 'Dashboard', confidence: 0.7 };
  return null;
}

// Try to extract a bare JSON object from message text that looks like GenUI props.
// Handles the case where LLM outputs raw JSON without ```gen-ui fencing.
function tryExtractBareGenUI(text: string): { component: string; props: Record<string, unknown> } | null {
  const trimmed = text.trim();
  // Must start with { and end with } — entire message is JSON
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) return null;
  // Quick guard: reject very short or very long blobs
  if (trimmed.length < 20 || trimmed.length > 8000) return null;
  try {
    const obj = JSON.parse(trimmed);
    // If it already has "component", use standard path
    if (obj.component) return { component: obj.component, props: obj.props || {} };
    const result = inferGenUIComponent(obj);
    if (result && result.confidence >= 0.6) return { component: result.component, props: obj };
  } catch { /* not valid JSON */ }
  return null;
}

function stripMarkdownLight(text: string) {
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[#>*_`[\]()]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function buildAssistantDigest(content: string) {
  const lines = content
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  const conclusion = stripMarkdownLight(
    lines.find((line) => !/^[-*\d.]+\s*$/.test(line) && !line.startsWith('|')) || content,
  ).slice(0, 180);
  const actionLines = lines
    .filter((line) => /下一步|建议|优先|需要|请|行动|处理|复核|生成/.test(line))
    .slice(0, 3)
    .map(stripMarkdownLight)
    .filter(Boolean);

  return {
    conclusion: conclusion || 'AI 已生成回复。',
    actions: actionLines.length > 0 ? actionLines : ['展开查看完整依据，再选择下一步操作。'],
  };
}

interface MessageBubbleProps {
  message: AIMessage;
  onCopy: (content: string) => void;
  onRegenerate?: () => void;
  onRetry?: () => void;
  onFeedback?: (type: 'positive' | 'negative', messageId: string) => void;
  onDelete?: (messageId: string) => void;
  onSendMessage?: (prompt: string) => void;
  onEditMessage?: (messageId: string, newContent: string) => void;
  onSwitchBranch?: (parentMessageId: string, branchIndex: number) => void;
  branchInfo?: { total: number; current: number } | null;
  isLatest?: boolean;
  isTyping?: boolean;
}

export const MessageBubble = React.memo(function MessageBubble({
  message,
  onCopy,
  onRegenerate,
  onRetry,
  onFeedback,
  onDelete,
  onSendMessage,
  onEditMessage,
  onSwitchBranch,
  branchInfo,
  isLatest,
  isTyping,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [showFullAssistantResult, setShowFullAssistantResult] = useState(false);
  const [editContent, setEditContent] = useState('');
  const isUser = message.role === 'user';
  const isStreamingNow = !!(isTyping && isLatest);

  // Memoize bare GenUI extraction to avoid re-parsing JSON on every render
  const bareGenUI = useMemo(
    () => (!isUser && message.content) ? tryExtractBareGenUI(message.content) : null,
    [isUser, message.content]
  );
  const shouldCompactAssistantResult = !isUser && !isStreamingNow && !bareGenUI && message.content.length > 900;
  const assistantDigest = useMemo(
    () => shouldCompactAssistantResult ? buildAssistantDigest(message.content) : null,
    [shouldCompactAssistantResult, message.content],
  );

  // Memoize markdown components to avoid re-creating on every render
  const markdownComponents = useMemo(() => ({
    code({ node, inline, className, children, ...props }: React.ClassAttributes<HTMLElement> & React.HTMLAttributes<HTMLElement> & { inline?: boolean, node?: unknown }) {
      const match = /language-(\w+[-]?\w*)/.exec(className || '');
      const lang = match?.[1]?.toLowerCase() || '';
      const raw = String(children).trim();
      const isGenUITag = ['gen-ui', 'gen', 'genui', 'gen_ui'].includes(lang);
      const isGenUIContent = !inline && !isGenUITag && raw.startsWith('{') &&
        /^\s*\{\s*"component"\s*:/.test(raw);
      if (isGenUITag || isGenUIContent) {
        try {
          const config = JSON.parse(raw);
          if (config.component && typeof config.component === 'string') {
            return <GenUIContainer componentName={config.component} props={config.props || {}} onSendMessage={onSendMessage} thinkingSteps={message.thinkingSteps} />;
          }
          const inferred = inferGenUIComponent(config);
          if (inferred && inferred.confidence >= 0.6) {
            return <GenUIContainer componentName={inferred.component} props={config} onSendMessage={onSendMessage} thinkingSteps={message.thinkingSteps} />;
          }
          if (config.title && Array.isArray(config.content)) {
            return (
              <div className="my-4 w-full overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                <div className="bg-muted/50 px-4 py-3 border-b border-border flex items-center gap-2">
                  <div className="h-5 w-1 bg-primary rounded-full"></div>
                  <h3 className="font-medium text-sm">{config.title}</h3>
                </div>
                <div className="p-4 space-y-2 text-sm text-muted-foreground leading-relaxed">
                  {config.content.map((item: unknown, i: number) => (
                    <div key={i}>{String(item)}</div>
                  ))}
                </div>
              </div>
            );
          }
          if (isGenUITag) {
            console.warn("GenUI Missing Component or Prop structure:", raw);
            return (
              <div className="my-4 w-full rounded-xl border border-amber-500/30 bg-amber-50 dark:bg-amber-950/20 p-4 text-sm text-amber-700 dark:text-amber-400">
                组件数据格式异常，无法渲染卡片，正在以文本形式展示...
                <pre className="mt-2 text-xs overflow-auto opacity-70 bg-black/5 dark:bg-white/5 p-2 rounded">{raw}</pre>
              </div>
            );
          }
        } catch {
          if (isStreamingNow) {
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
          if (isGenUITag) {
            console.error("GenUI Parse Error:", raw);
            return (
              <div className="my-4 w-full rounded-xl border border-amber-500/30 bg-amber-50 dark:bg-amber-950/20 p-4 text-sm text-amber-700 dark:text-amber-400">
                组件加载失败，正在尝试解析...
              </div>
            );
          }
        }
      }
      return !inline && match ? (
        <div className="relative rounded-md overflow-hidden my-2">
          <div className="flex items-center justify-between px-3 py-1 bg-zinc-900 border-b border-zinc-700">
            <span className="text-xs text-zinc-400">{match[1]}</span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(String(children)).catch(() => {});
                toast.success("代码已复制");
              }}
              className="text-xs text-zinc-400 hover:text-white"
            >
              <Copy className="w-3 h-3" />
            </button>
          </div>
          <LazyCodeBlock language={match[1]} {...props}>
            {String(children).replace(/\n$/, '')}
          </LazyCodeBlock>
        </div>
      ) : (
        <code className={cn("bg-muted/50 px-1 py-0.5 rounded font-mono text-sm", className)} {...props}>
          {children}
        </code>
      );
    },
    a: ({ node, ...props }: React.ComponentPropsWithoutRef<'a'> & { node?: unknown }) => (
      <a target="_blank" rel="noopener noreferrer" className="underline decoration-dotted underline-offset-4 hover:decoration-solid" {...props} />
    ),
    table: ({ node, ...props }: React.ComponentPropsWithoutRef<'table'> & { node?: unknown }) => (
      <div className="overflow-x-auto my-4 border rounded-md">
        <table className="w-full text-sm text-left" {...props} />
      </div>
    ),
    th: ({ node, ...props }: React.ComponentPropsWithoutRef<'th'> & { node?: unknown }) => (
      <th className="border-b bg-muted/50 px-4 py-2 font-medium" {...props} />
    ),
    td: ({ node, ...props }: React.ComponentPropsWithoutRef<'td'> & { node?: unknown }) => (
      <td className="border-b px-4 py-2" {...props} />
    ),
    blockquote: ({ node, ...props }: React.ComponentPropsWithoutRef<'blockquote'> & { node?: unknown }) => (
      <blockquote className="border-l-4 border-primary/30 pl-4 py-1 my-2 italic bg-muted/20 rounded-r" {...props} />
    ),
  }), [onSendMessage, message.thinkingSteps, isStreamingNow]);

  const handleCopy = () => {
    onCopy(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedback = (type: 'positive' | 'negative') => {
    setFeedback(type);
    onFeedback?.(type, message.id);
    toast.success(type === 'positive' ? '感谢您的反馈！' : '我们会继续改进');
  };

  return (
    <div
      className={cn(
        'group mb-5 flex min-w-0 gap-3',
        isUser ? 'justify-end' : 'justify-start',
        getEnterAnimationClass('fade', 'fast')
      )}
    >
      {!isUser && (
        <div className="relative mt-1 flex-shrink-0">
          <div className="relative z-10 flex h-8 w-8 items-center justify-center rounded-md border border-primary/15 bg-primary/[0.07] shadow-[0_1px_2px_hsl(var(--primary)/0.08)]">
            <Bot className="h-4 w-4 text-primary" />
          </div>
          {/* AI 状态呼吸灯 */}
          {isTyping && isLatest && (
            <div className="absolute -bottom-0.5 -right-0.5 z-20 h-2.5 w-2.5 rounded-full border-2 border-card bg-success" />
          )}
        </div>
      )}

      <div className={cn('flex min-w-0 flex-col', isUser ? 'max-w-[84%] items-end' : 'w-full max-w-none')}>
        {!isUser && message.agent && (
          <div className="flex items-center gap-2 mb-1.5 pl-1.5">
            {message.isProactive && (
              <span className="rounded border border-primary/15 bg-primary/[0.07] px-1.5 py-0.5 text-[10px] font-medium text-primary">
                AI 主动建议
              </span>
            )}
            <span className="text-xs font-semibold text-foreground/80 tracking-wide">{message.agent}</span>
            <span className="text-[10px] text-muted-foreground/60 font-mono">
              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        )}

        {isUser && (
           <div className="flex items-center gap-2 mb-1.5 pr-1.5">
             <span className="text-[10px] text-muted-foreground/60 font-mono">
               {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
             </span>
             <span className="text-xs font-semibold text-foreground/80 tracking-wide">我</span>
           </div>
        )}

        <div
          className={cn(
            'group/bubble relative min-w-0 rounded-lg px-4 py-3.5',
            isUser
              ? 'bg-primary text-primary-foreground shadow-[0_2px_8px_hsl(var(--primary)/0.16)] chat-bubble-user'
              : 'w-full border bg-card text-card-foreground shadow-[var(--shadow-card)] chat-bubble-ai'
          )}
        >
          {/* 用户附件显示优化 */}
          {isUser && message.imageUrls && message.imageUrls.length > 0 && !isEditing && (
            <div className="flex gap-2 flex-wrap mb-3">
              {message.imageUrls.map((url, i) => (
                <div key={i} className="relative group/img overflow-hidden rounded-md border border-white/20 shadow-sm">
                  <img
                    src={url}
                    alt={`附件 ${i + 1}`}
                    className="max-h-[180px] max-w-[240px] cursor-zoom-in object-cover"
                    onClick={() => window.open(url, '_blank')}
                  />
                </div>
              ))}
            </div>
          )}
          {/* Edit mode for user messages */}
          {isUser && isEditing ? (
            <div className="flex flex-col gap-2">
              <textarea
                className="w-full bg-primary-foreground/10 text-primary-foreground rounded-lg p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-foreground/30 min-h-[60px]"
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (editContent.trim() && editContent.trim() !== message.content) {
                      onEditMessage?.(message.id, editContent.trim());
                    }
                    setIsEditing(false);
                  }
                  if (e.key === 'Escape') {
                    setIsEditing(false);
                  }
                }}
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs text-primary-foreground/70"
                  onClick={() => setIsEditing(false)}
                >
                  取消
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-6 px-3 text-xs"
                  disabled={!editContent.trim() || editContent.trim() === message.content}
                  onClick={() => {
                    if (editContent.trim() && editContent.trim() !== message.content) {
                      onEditMessage?.(message.id, editContent.trim());
                    }
                    setIsEditing(false);
                  }}
                >
                  发送
                </Button>
              </div>
            </div>
          ) : message.status === 'error' ? (
            <div className="flex flex-col items-center gap-2 py-1">
              <div className="flex items-center gap-2 text-destructive">
                <AlertCircle className="w-4 h-4" />
                <span className="text-sm">{message.errorMessage || '发送失败'}</span>
              </div>
              {onRetry && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-3 text-xs gap-1.5"
                  onClick={onRetry}
                >
                  <RefreshCw className="w-3 h-3" />
                  重试
                </Button>
              )}
            </div>
          ) : isTyping && isLatest && !message.content ? (
            <div className="flex flex-col gap-2 min-w-[200px]">
              <ExecutionPulse 
                type={message.thinkingSteps?.some(s => s.tool_name?.includes('search')) ? 'searching' : 'thinking'}
                label={message.thinkingSteps?.filter(s => s.tool_name).pop()?.tool_name 
                  ? `正在调用: ${message.thinkingSteps.filter(s => s.tool_name).pop()?.tool_name}` 
                  : "正在思考..."
                }
                sublabel="Nexus AI 处理中"
              />
            </div>
          ) : shouldCompactAssistantResult && assistantDigest && !showFullAssistantResult ? (
            <div data-testid="assistant-compact-result" className="space-y-3">
              <div className="rounded-md border bg-background/70 p-3">
                <div className="text-xs font-semibold text-primary">结论</div>
                <p className="mt-1 text-sm leading-6">{assistantDigest.conclusion}</p>
              </div>
              <div className="rounded-md border bg-background/70 p-3">
                <div className="text-xs font-semibold text-primary">下一步</div>
                <ul className="mt-1 space-y-1 text-sm leading-6 text-muted-foreground">
                  {assistantDigest.actions.map((action, index) => (
                    <li key={`${message.id}-action-${index}`}>{action}</li>
                  ))}
                </ul>
              </div>
              <Button
                size="sm"
                variant="ghost"
                className="h-8 px-2 text-xs"
                onClick={() => setShowFullAssistantResult(true)}
              >
                展开完整依据
                <ChevronDown className="ml-1.5 h-3.5 w-3.5" />
              </Button>
            </div>
          ) : (
            (() => {
              // Layer 0: Use memoized bare JSON detection result
              if (bareGenUI) {
                return <GenUIContainer componentName={bareGenUI.component} props={bareGenUI.props} onSendMessage={onSendMessage} thinkingSteps={message.thinkingSteps} />;
              }
              return null;
            })() ||
            <div className={cn("prose prose-sm max-w-none dark:prose-invert break-words", isUser && "text-primary-foreground prose-headings:text-primary-foreground prose-a:text-primary-foreground prose-strong:text-primary-foreground prose-code:text-primary-foreground/90")}>
              <StreamingMarkdown
                content={message.content}
                isStreaming={isStreamingNow}
                components={markdownComponents}
              />
              {shouldCompactAssistantResult && showFullAssistantResult && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="mt-3 h-8 px-2 text-xs"
                  onClick={() => setShowFullAssistantResult(false)}
                >
                  收起依据
                  <ChevronUp className="ml-1.5 h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          )}
        </div>

        {/* Action Bar for Assistant Messages */}
        {!isUser && message.content && (
          <>
            {/* Inline Actions from related tools */}
            {onSendMessage && !isTyping && message.thinkingSteps?.some(s => s.tool_name) && (
              <InlineActions
                toolName={message.thinkingSteps.filter(s => s.tool_name).pop()!.tool_name!}
                onAction={onSendMessage}
              />
            )}

            {/* Branch Navigator */}
            {branchInfo && branchInfo.total > 1 && (
              <div className="flex items-center gap-1 mt-1.5 text-xs text-muted-foreground">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-5 w-5 p-0"
                  disabled={branchInfo.current <= 0}
                  onClick={() => onSwitchBranch?.(message.parentId ?? '', branchInfo.current - 1)}
                >
                  <ChevronLeft className="w-3 h-3" />
                </Button>
                <span>{branchInfo.current + 1}/{branchInfo.total}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-5 w-5 p-0"
                  disabled={branchInfo.current >= branchInfo.total - 1}
                  onClick={() => onSwitchBranch?.(message.parentId ?? '', branchInfo.current + 1)}
                >
                  <ChevronRight className="w-3 h-3" />
                </Button>
              </div>
            )}

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
                  aria-label="复制消息"
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
                  onClick={() => onDelete?.(message.id)}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  删除消息
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          </>
        )}
      </div>
      
      {isUser && (
        <div className="flex items-center gap-1 flex-shrink-0 mt-1">
          {/* Edit button for user messages */}
          {onEditMessage && !isEditing && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => { setEditContent(message.content); setIsEditing(true); }}
                >
                  <Pencil className="w-3 h-3" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">编辑</TooltipContent>
            </Tooltip>
          )}
          <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center border border-border">
            <User className="w-4 h-4 text-muted-foreground" />
          </div>
        </div>
      )}
    </div>
  );
});

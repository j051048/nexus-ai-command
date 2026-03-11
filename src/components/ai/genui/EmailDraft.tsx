import React, { useState } from 'react';
import { Mail, Bell, MessageCircle, Copy, Check, Pencil } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmailDraftProps {
  to: string;
  cc?: string;
  subject: string;
  body: string;
  type?: 'email' | 'notification' | 'wechat';
}

const typeConfig = {
  email: { icon: Mail, label: '邮件草稿', accent: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-500/10' },
  notification: { icon: Bell, label: '通知草稿', accent: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-500/10' },
  wechat: { icon: MessageCircle, label: '消息草稿', accent: 'text-green-600 dark:text-green-400', bg: 'bg-green-500/10' },
};

export function EmailDraft({ to, cc, subject, body, type = 'email' }: EmailDraftProps) {
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState(body);

  const config = typeConfig[type] || typeConfig.email;
  const Icon = config.icon;

  const handleCopy = async () => {
    const fullText = [
      `收件人: ${to}`,
      cc ? `抄送: ${cc}` : '',
      `主题: ${subject}`,
      '',
      editing ? editBody : body,
    ].filter(Boolean).join('\n');

    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for environments without clipboard API
      const textarea = document.createElement('textarea');
      textarea.value = fullText;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={cn('rounded-lg p-1.5', config.bg)}>
            <Icon className={cn('w-4 h-4', config.accent)} />
          </div>
          <span className={cn('text-xs font-medium', config.accent)}>{config.label}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setEditing(!editing)}
            className={cn(
              'inline-flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors',
              editing
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-input bg-background text-foreground hover:bg-accent',
            )}
          >
            <Pencil className="w-3 h-3" />
            {editing ? '完成编辑' : '编辑'}
          </button>
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors"
          >
            {copied ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
            {copied ? '已复制' : '复制全文'}
          </button>
        </div>
      </div>

      {/* Meta fields */}
      <div className="rounded-lg border bg-muted/30 px-3 py-2.5 space-y-1.5 text-sm">
        <div className="flex gap-2">
          <span className="text-muted-foreground shrink-0 w-12">收件人</span>
          <span className="font-medium truncate">{to}</span>
        </div>
        {cc && (
          <div className="flex gap-2">
            <span className="text-muted-foreground shrink-0 w-12">抄送</span>
            <span className="truncate">{cc}</span>
          </div>
        )}
        <div className="flex gap-2">
          <span className="text-muted-foreground shrink-0 w-12">主题</span>
          <span className="font-medium">{subject}</span>
        </div>
      </div>

      {/* Body */}
      {editing ? (
        <textarea
          value={editBody}
          onChange={e => setEditBody(e.target.value)}
          className="w-full min-h-[120px] rounded-lg border bg-background px-3 py-2.5 text-sm leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      ) : (
        <div className="text-sm leading-relaxed whitespace-pre-wrap px-1">
          {editing ? editBody : body}
        </div>
      )}
    </div>
  );
}

export default EmailDraft;

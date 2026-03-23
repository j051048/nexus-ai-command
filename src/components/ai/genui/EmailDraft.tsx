import React, { useState } from 'react';
import { Mail, MessageSquare, Send, Copy, CheckCircle2, User, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export interface EmailDraftProps {
  to?: string;
  cc?: string;
  subject?: string;
  body: string;
  type?: 'email' | 'notification' | 'wechat';
}

export default function EmailDraft({ to, cc, subject, body, type = 'email' }: EmailDraftProps) {
  const [copied, setCopied] = useState(false);
  const [sent, setSent] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(body).catch(() => {});
    setCopied(true);
    toast.success('正文已复制到剪贴板');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSend = () => {
    setSent(true);
    toast.success(type === 'email' ? '邮件已发送' : '消息已发送');
  };

  const isEmail = type === 'email';
  const Icon = type === 'wechat' ? MessageSquare : (type === 'notification' ? Clock : Mail);

  if (sent) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-muted/10 border border-border/50 rounded-xl">
        <div className="w-12 h-12 bg-green-500/20 text-green-500 rounded-full flex items-center justify-center mb-3">
          <CheckCircle2 className="w-6 h-6" />
        </div>
        <h3 className="text-lg font-medium text-foreground">发送成功</h3>
        <p className="text-sm text-muted-foreground mt-1">草稿已成功投递至目标方</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-full bg-card rounded-xl border border-border/50 overflow-hidden shadow-sm">
      <div className="bg-muted/30 px-4 py-3 border-b border-border flex items-center gap-2">
        <Icon className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">{isEmail ? '邮件草稿' : '消息草稿'}</span>
        <div className="ml-auto pointer-events-none">
          <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full uppercase font-medium">Draft</span>
        </div>
      </div>

      <div className="p-4 space-y-3 border-b border-border/50 text-sm">
        {to && (
          <div className="flex items-start gap-4">
            <span className="text-muted-foreground w-12 flex-shrink-0 mt-0.5">收件人</span>
            <div className="flex flex-wrap gap-1">
              {to.split(/[,;]/).map((t, i) => (
                <span key={i} className="inline-flex items-center gap-1 bg-secondary px-2 py-0.5 rounded-md text-secondary-foreground text-xs">
                  <User className="w-3 h-3" />
                  {t.trim()}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {cc && isEmail && (
          <div className="flex items-start gap-4">
            <span className="text-muted-foreground w-12 flex-shrink-0 mt-0.5">抄送</span>
            <div className="flex flex-wrap gap-1">
              {cc.split(/[,;]/).map((c, i) => (
                <span key={i} className="inline-flex items-center gap-1 bg-secondary/50 px-2 py-0.5 rounded-md text-secondary-foreground text-xs">
                  <User className="w-3 h-3" />
                  {c.trim()}
                </span>
              ))}
            </div>
          </div>
        )}

        {subject && (
          <div className="flex items-start gap-4">
            <span className="text-muted-foreground w-12 flex-shrink-0">主题</span>
            <span className="font-medium text-foreground">{subject}</span>
          </div>
        )}
      </div>

      <div className="p-4 bg-background min-h-[120px]">
        <div className="whitespace-pre-wrap text-sm text-foreground/90 leading-relaxed font-sans">
          {body}
        </div>
      </div>

      <div className="bg-muted/10 p-3 border-t border-border flex items-center justify-end gap-2">
        <Button variant="outline" size="sm" onClick={handleCopy} className="text-xs h-8">
          <Copy className="w-3.5 h-3.5 mr-1.5" />
          {copied ? '已复制' : '复制正文'}
        </Button>
        <Button size="sm" onClick={handleSend} className="text-xs h-8">
          <Send className="w-3.5 h-3.5 mr-1.5" />
          发送{isEmail ? '邮件' : '消息'}
        </Button>
      </div>
    </div>
  );
}

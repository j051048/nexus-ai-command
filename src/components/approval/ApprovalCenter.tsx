import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Send,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Plane,
  ShoppingCart,
  Receipt,
  Calendar,
  Bot,
  Sparkles,
} from 'lucide-react';

const approvalTypes = [
  { id: 'travel', name: '出差申请', icon: <Plane className="w-5 h-5" />, example: '下周去上海出差见客户，预算2500，包括高铁和酒店' },
  { id: 'purchase', name: '采购申请', icon: <ShoppingCart className="w-5 h-5" />, example: '采购一台示波器，型号DSO1104，预算8000元' },
  { id: 'expense', name: '费用报销', icon: <Receipt className="w-5 h-5" />, example: '报销上周客户拜访餐费320元，附发票' },
  { id: 'leave', name: '请假申请', icon: <Calendar className="w-5 h-5" />, example: '申请下周一年假一天，处理私事' },
];

const mockHistory = [
  { id: '1', type: 'travel', description: '北京出差见客户', amount: 2300, status: 'auto_approved', time: '2小时前' },
  { id: '2', type: 'purchase', description: '采购测试用电缆', amount: 450, status: 'auto_approved', time: '昨天' },
  { id: '3', type: 'expense', description: '客户接待餐费', amount: 680, status: 'requires_boss', time: '昨天' },
  { id: '4', type: 'travel', description: '深圳参加展会', amount: 4200, status: 'auto_approved', time: '3天前' },
  { id: '5', type: 'leave', description: '年假2天', amount: 0, status: 'auto_approved', time: '5天前' },
];

const statusConfig = {
  auto_approved: { label: '已自动通过', color: 'bg-success/20 text-success', icon: <CheckCircle2 className="w-4 h-4" /> },
  requires_boss: { label: '已推送老板', color: 'bg-warning/20 text-warning', icon: <Clock className="w-4 h-4" /> },
  pending: { label: '处理中', color: 'bg-primary/20 text-primary', icon: <Clock className="w-4 h-4" /> },
};

export function ApprovalCenter() {
  const [input, setInput] = useState('');
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  const handleSubmit = () => {
    if (!input.trim()) return;
    
    setIsProcessing(true);
    setResult(null);

    // Simulate AI processing
    setTimeout(() => {
      setIsProcessing(false);
      setResult({
        success: true,
        message: '已自动审批通过！预订确认信息将发送至您的邮箱。',
      });
      setInput('');
    }, 2000);
  };

  const useExample = (example: string, typeId: string) => {
    setInput(example);
    setSelectedType(typeId);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">智能审批中心</h1>
        <p className="text-muted-foreground mt-1">一句话提交，AI秒速处理</p>
      </div>

      {/* Quick Submit */}
      <div className="bg-gradient-card rounded-2xl p-6 cyber-border">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center">
            <Bot className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">AI审批管家</h2>
            <p className="text-xs text-muted-foreground">用自然语言描述您的需求，AI自动识别并处理</p>
          </div>
        </div>

        {/* Type Shortcuts */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          {approvalTypes.map((type) => (
            <button
              key={type.id}
              onClick={() => useExample(type.example, type.id)}
              className={cn(
                "p-4 rounded-xl border transition-all text-left",
                selectedType === type.id
                  ? "border-primary bg-primary/10"
                  : "border-border bg-secondary/50 hover:border-primary/50"
              )}
            >
              <div className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center mb-3",
                selectedType === type.id ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
              )}>
                {type.icon}
              </div>
              <p className="font-medium text-foreground text-sm">{type.name}</p>
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{type.example}</p>
            </button>
          ))}
        </div>

        {/* Input Area */}
        <div className="relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="描述您的申请，例如：下周二出差去上海拜访复旦大学客户，预算3000元，含高铁和酒店..."
            className="w-full h-32 bg-secondary rounded-xl p-4 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || isProcessing}
            className={cn(
              "absolute bottom-4 right-4 px-6 py-2 rounded-lg font-medium transition-all flex items-center gap-2",
              input.trim() && !isProcessing
                ? "bg-gradient-primary text-primary-foreground glow-primary"
                : "bg-muted text-muted-foreground"
            )}
          >
            {isProcessing ? (
              <>
                <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                AI处理中...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                提交申请
              </>
            )}
          </button>
        </div>

        {/* Result */}
        {result && (
          <div className={cn(
            "mt-4 p-4 rounded-xl flex items-start gap-3 animate-fade-in",
            result.success ? "bg-success/10 border border-success/30" : "bg-destructive/10 border border-destructive/30"
          )}>
            <div className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
              result.success ? "bg-success/20 text-success" : "bg-destructive/20 text-destructive"
            )}>
              {result.success ? <CheckCircle2 className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
            </div>
            <div>
              <p className={cn("font-medium", result.success ? "text-success" : "text-destructive")}>
                {result.success ? '审批完成' : '需要补充信息'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">{result.message}</p>
            </div>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-card rounded-xl p-5 border border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">本月审批</p>
              <p className="text-2xl font-bold text-foreground mt-1">28</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
              <CheckCircle2 className="w-6 h-6 text-primary" />
            </div>
          </div>
        </div>
        <div className="bg-card rounded-xl p-5 border border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">自动通过率</p>
              <p className="text-2xl font-bold text-success mt-1">96%</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-success/20 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-success" />
            </div>
          </div>
        </div>
        <div className="bg-card rounded-xl p-5 border border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">平均处理时间</p>
              <p className="text-2xl font-bold text-foreground mt-1">3秒</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
              <Clock className="w-6 h-6 text-primary" />
            </div>
          </div>
        </div>
      </div>

      {/* History */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">审批记录</h2>
          <button className="text-sm text-primary hover:underline">查看全部</button>
        </div>

        <div className="space-y-3">
          {mockHistory.map((item) => {
            const status = statusConfig[item.status as keyof typeof statusConfig];
            return (
              <div
                key={item.id}
                className="flex items-center gap-4 p-4 rounded-xl bg-secondary/50 hover:bg-secondary transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                  {item.type === 'travel' && <Plane className="w-5 h-5" />}
                  {item.type === 'purchase' && <ShoppingCart className="w-5 h-5" />}
                  {item.type === 'expense' && <Receipt className="w-5 h-5" />}
                  {item.type === 'leave' && <Calendar className="w-5 h-5" />}
                </div>
                <div className="flex-1">
                  <p className="font-medium text-foreground">{item.description}</p>
                  <p className="text-xs text-muted-foreground">{item.time}</p>
                </div>
                {item.amount > 0 && (
                  <p className="text-sm font-medium text-foreground mono-number">¥{item.amount}</p>
                )}
                <div className={cn("flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium", status.color)}>
                  {status.icon}
                  {status.label}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

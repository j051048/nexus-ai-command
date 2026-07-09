'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';
import {
  Bot,
  MessageSquare,
  Layout,
  AtSign,
  Command,
  ChevronRight,
  ChevronLeft,
  X,
  Sparkles,
  Rocket,
  Zap,
  Users,
  BarChart3,
  Shield,
  Keyboard,
  Search,
  Database,
  Loader2,
} from 'lucide-react';

const STORAGE_KEY = 'nexus_onboarding_completed';

interface WelcomeTourStep {
  title: string;
  description: string;
  icon: React.ReactNode;
  illustration: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Illustrations - composed from lucide icons
// ---------------------------------------------------------------------------

function WelcomeIllustration() {
  return (
    <div className="relative flex items-center justify-center w-full h-40">
      {/* Glow ring */}
      <div className="absolute w-28 h-28 rounded-full bg-primary/10 animate-pulse-glow" />
      <div className="absolute w-20 h-20 rounded-full bg-primary/20" />
      {/* Orbiting sparkles */}
      <Sparkles className="absolute top-4 right-16 w-5 h-5 text-yellow-400 animate-bounce" />
      <Sparkles className="absolute bottom-6 left-16 w-4 h-4 text-yellow-400 animate-bounce [animation-delay:300ms]" />
      {/* Center rocket */}
      <Rocket className="relative z-10 w-14 h-14 text-primary drop-shadow-lg" />
    </div>
  );
}

function AIChatIllustration() {
  return (
    <div className="relative flex items-center justify-center w-full h-40">
      {/* Chat bubble backdrop */}
      <div className="absolute w-32 h-24 rounded-2xl bg-primary/5 border border-primary/10 -rotate-3" />
      <div className="relative z-10 flex flex-col items-center gap-2">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-full bg-primary/15 flex items-center justify-center">
            <Bot className="w-6 h-6 text-primary" />
          </div>
          <div className="flex flex-col gap-1">
            <div className="h-2 w-20 rounded bg-muted" />
            <div className="h-2 w-14 rounded bg-muted" />
          </div>
        </div>
        <div className="flex items-center gap-2 self-end">
          <div className="flex flex-col gap-1 items-end">
            <div className="h-2 w-16 rounded bg-primary/30" />
            <div className="h-2 w-10 rounded bg-primary/30" />
          </div>
          <MessageSquare className="w-5 h-5 text-primary/60" />
        </div>
      </div>
      <Sparkles className="absolute top-2 right-14 w-4 h-4 text-yellow-400/70 animate-bounce [animation-delay:200ms]" />
    </div>
  );
}

function WorkspaceIllustration() {
  return (
    <div className="relative flex items-center justify-center w-full h-40">
      {/* Window frame */}
      <div className="relative w-44 h-28 rounded-lg border border-border bg-card shadow-md overflow-hidden">
        {/* Title bar */}
        <div className="h-5 bg-muted/60 border-b border-border flex items-center gap-1 px-2">
          <div className="w-1.5 h-1.5 rounded-full bg-destructive/60" />
          <div className="w-1.5 h-1.5 rounded-full bg-warning/60" />
          <div className="w-1.5 h-1.5 rounded-full bg-success/60" />
        </div>
        {/* Content mockup */}
        <div className="p-2 flex gap-2">
          <div className="flex flex-col gap-1.5 flex-1">
            <div className="h-2 w-full rounded bg-muted" />
            <div className="h-2 w-3/4 rounded bg-muted" />
            <div className="h-6 w-full rounded bg-primary/10 mt-1" />
          </div>
          <div className="w-12 flex flex-col gap-1">
            <BarChart3 className="w-full h-8 text-primary/40" />
            <div className="h-2 w-full rounded bg-muted" />
          </div>
        </div>
      </div>
      <Layout className="absolute -bottom-1 -right-1 w-6 h-6 text-primary/50" />
    </div>
  );
}

function AgentIllustration() {
  return (
    <div className="relative flex items-center justify-center w-full h-40">
      {/* Central @ symbol */}
      <div className="absolute w-16 h-16 rounded-full bg-primary/10" />
      <AtSign className="relative z-10 w-10 h-10 text-primary" />
      {/* Agent tags orbiting around */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 -translate-y-1 flex gap-1">
        <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 text-[10px] font-medium border border-blue-500/20">
          销售助手
        </span>
      </div>
      <div className="absolute bottom-5 left-8">
        <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-600 text-[10px] font-medium border border-green-500/20">
          绩效助手
        </span>
      </div>
      <div className="absolute bottom-5 right-8">
        <span className="px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-600 text-[10px] font-medium border border-purple-500/20">
          审批助手
        </span>
      </div>
      <Users className="absolute top-6 right-12 w-4 h-4 text-muted-foreground/50" />
      <Shield className="absolute top-6 left-12 w-4 h-4 text-muted-foreground/50" />
    </div>
  );
}

function ShortcutIllustration() {
  return (
    <div className="relative flex items-center justify-center w-full h-40">
      {/* Keyboard keys */}
      <div className="flex items-center gap-2">
        <div className="w-12 h-12 rounded-lg border-2 border-border bg-card shadow-sm flex items-center justify-center">
          <Command className="w-6 h-6 text-primary" />
        </div>
        <span className="text-lg font-bold text-muted-foreground">+</span>
        <div className="w-12 h-12 rounded-lg border-2 border-border bg-card shadow-sm flex items-center justify-center">
          <Keyboard className="w-6 h-6 text-primary" />
        </div>
      </div>
      {/* Floating action hints */}
      <div className="absolute bottom-4 flex items-center gap-3 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1"><Search className="w-3 h-3" /> 搜索</span>
        <span className="flex items-center gap-1"><Zap className="w-3 h-3" /> 快捷操作</span>
        <span className="flex items-center gap-1"><Rocket className="w-3 h-3" /> 导航</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Steps definition
// ---------------------------------------------------------------------------

const steps: WelcomeTourStep[] = [
  {
    title: '欢迎使用 Nexus AI',
    description:
      'Nexus AI 是一款 AI 驱动的企业管理平台，让智能助手帮您完成日常工作。接下来花 30 秒快速了解核心功能。',
    icon: <Rocket className="w-5 h-5" />,
    illustration: <WelcomeIllustration />,
  },
  {
    title: '左侧是您的 AI 助手',
    description:
      '通过自然语言对话，即可完成审批、查询销售数据、生成报表等操作。无需记菜单，说出您的需求即可。',
    icon: <Bot className="w-5 h-5" />,
    illustration: <AIChatIllustration />,
  },
  {
    title: '右侧是您的工作空间',
    description:
      'Canvas 区域会展示具体的功能页面——仪表盘、销售看板、审批列表等，AI 会自动为您打开对应页面。',
    icon: <Layout className="w-5 h-5" />,
    illustration: <WorkspaceIllustration />,
  },
  {
    title: '输入 @ 选择专属 AI 助手',
    description:
      '在聊天框输入 @，可选择不同专业助手：销售助手、绩效助手、审批助手等，各司其职更高效。',
    icon: <AtSign className="w-5 h-5" />,
    illustration: <AgentIllustration />,
  },
  {
    title: '使用 Ctrl+K 打开命令面板',
    description:
      '随时按 Ctrl+K（Mac: ⌘K）呼出命令面板，快速搜索功能、跳转页面或执行操作，效率倍增。',
    icon: <Command className="w-5 h-5" />,
    illustration: <ShortcutIllustration />,
  },
];

// ---------------------------------------------------------------------------
// WelcomeTour component
// ---------------------------------------------------------------------------

export function WelcomeTour() {
  const [isVisible, setIsVisible] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [direction, setDirection] = useState<'next' | 'prev'>('next');
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    try {
      const completed = localStorage.getItem(STORAGE_KEY);
      if (!completed) {
        const timer = setTimeout(() => setIsVisible(true), 500);
        return () => clearTimeout(timer);
      }
    } catch {
      // localStorage not available — silently ignore
    }
  }, []);

  const complete = useCallback(() => {
    try {
      localStorage.setItem(STORAGE_KEY, 'true');
    } catch {
      // ignore
    }
    setIsVisible(false);
  }, []);

  const generateDemoData = useCallback(async () => {
    setGenerating(true);
    try {
      await aiClient.fetch('api/onboarding/generate-demo-data', { method: 'POST' });
      toast.success('Demo data generated! Explore the platform with sample data.');
      complete();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to generate demo data');
    } finally {
      setGenerating(false);
    }
  }, [complete]);

  const goNext = useCallback(() => {
    if (currentStep < steps.length - 1) {
      setDirection('next');
      setCurrentStep((s) => s + 1);
    } else {
      complete();
    }
  }, [currentStep, complete]);

  const goPrev = useCallback(() => {
    if (currentStep > 0) {
      setDirection('prev');
      setCurrentStep((s) => s - 1);
    }
  }, [currentStep]);

  if (!isVisible) return null;

  const step = steps[currentStep];
  const isFirst = currentStep === 0;
  const isLast = currentStep === steps.length - 1;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in"
        onClick={complete}
        aria-hidden
      />

      {/* Card */}
      <div
        className={cn(
          'relative z-10 w-full max-w-md rounded-2xl border border-border bg-card shadow-2xl overflow-hidden',
          'animate-scale-in'
        )}
      >
        {/* Skip button */}
        <button
          onClick={complete}
          className="absolute top-3 right-3 z-20 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          aria-label="跳过引导"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Step indicator dots */}
        <div className="flex justify-center gap-1.5 pt-5 pb-2">
          {steps.map((_, idx) => (
            <button
              key={idx}
              onClick={() => {
                setDirection(idx > currentStep ? 'next' : 'prev');
                setCurrentStep(idx);
              }}
              className={cn(
                'h-1.5 rounded-full transition-all duration-300',
                idx === currentStep
                  ? 'w-6 bg-primary'
                  : 'w-1.5 bg-muted-foreground/30 hover:bg-muted-foreground/50'
              )}
              aria-label={`步骤 ${idx + 1}`}
            />
          ))}
        </div>

        {/* Illustration area */}
        <div
          key={currentStep}
          className={cn(
            'px-6',
            direction === 'next'
              ? 'animate-slide-in-right'
              : 'animate-fade-in'
          )}
        >
          {step.illustration}
        </div>

        {/* Text content */}
        <div
          key={`text-${currentStep}`}
          className={cn(
            'px-6 pb-2 text-center',
            direction === 'next'
              ? 'animate-slide-in-right'
              : 'animate-fade-in'
          )}
        >
          <div className="inline-flex items-center gap-2 mb-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium">
            {step.icon}
            <span>步骤 {currentStep + 1}/{steps.length}</span>
          </div>
          <h2 className="text-xl font-bold text-foreground mb-2 tracking-tight">
            {step.title}
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {step.description}
          </p>
        </div>

        {/* Actions */}
        <div className="px-6 pb-6 pt-4 flex flex-col gap-3">
          {isLast && (
            <Button
              variant="outline"
              size="sm"
              onClick={generateDemoData}
              disabled={generating}
              className="w-full gap-2"
            >
              {generating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  正在生成...
                </>
              ) : (
                <>
                  <Database className="w-4 h-4" />
                  一键生成演示数据
                </>
              )}
            </Button>
          )}
          <div className="flex items-center justify-between">
            <div>
              {!isFirst && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={goPrev}
                  className="gap-1 text-muted-foreground"
                >
                  <ChevronLeft className="w-4 h-4" />
                  上一步
                </Button>
              )}
            </div>

            <Button
              size="sm"
              onClick={goNext}
              disabled={generating}
              className="gap-1 min-w-[100px]"
            >
              {isLast ? (
                <>
                  跳过，直接使用
                  <Sparkles className="w-4 h-4" />
                </>
              ) : (
                <>
                  下一步
                  <ChevronRight className="w-4 h-4" />
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default WelcomeTour;

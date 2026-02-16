/**
 * 移动端 AI 浮动操作按钮
 * 固定在右下角，点击唤起 AI 半屏面板
 */

import { Bot } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MobileAIFABProps {
  onClick: () => void;
  visible?: boolean;
}

export default function MobileAIFAB({ onClick, visible = true }: MobileAIFABProps) {
  if (!visible) return null;

  return (
    <button
      onClick={onClick}
      className={cn(
        'fixed z-40 w-12 h-12 rounded-full',
        'bg-primary text-primary-foreground',
        'shadow-lg shadow-primary/25',
        'flex items-center justify-center',
        'hover:bg-primary/90 hover:scale-105',
        'active:scale-95',
        'transition-all duration-200',
        'touch-manipulation',
        // 位置：底部 Tab 上方
        'bottom-[calc(4.5rem+env(safe-area-inset-bottom))] right-4'
      )}
      aria-label="打开 AI 助手"
    >
      <Bot className="w-5 h-5" />
    </button>
  );
}

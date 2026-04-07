import { Sparkles } from 'lucide-react';
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
        'fixed z-40 w-14 h-14 rounded-2xl',
        'bg-primary text-white',
        'shadow-[0_8px_30px_rgba(var(--primary-rgb),0.3)]',
        'flex items-center justify-center',
        'border border-white/20',
        'active:scale-90',
        'transition-all duration-300',
        'touch-manipulation',
        'animate-in fade-in zoom-in slide-in-from-bottom-5 duration-500',
        // 位置：底部 Tab 上方
        'bottom-[calc(5rem+env(safe-area-inset-bottom))] right-6'
      )}
      aria-label="打开 AI 数字化指挥部"
    >
      <div className="relative">
        <Sparkles className="w-6 h-6 animate-pulse" />
        <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-white rounded-full scale-0 animate-bounce group-active:scale-100" />
      </div>

      {/* Glossy overlay */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-white/10 via-transparent to-transparent pointer-events-none" />
    </button>
  );
}

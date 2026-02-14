import { useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { useSwipe } from '@/hooks/useMobile';

interface SwipeAction {
  label: string;
  icon?: ReactNode;
  color?: string;
  onClick: () => void;
}

interface SwipeableCardProps {
  children: ReactNode;
  /** 左滑时显示的操作按钮 */
  actions?: SwipeAction[];
  /** 滑动触发阈值 (px) */
  threshold?: number;
  /** 自定义 className */
  className?: string;
}

/**
 * 可左滑操作的卡片组件
 * 左滑显示操作按钮（如删除、批准、拒绝）
 * 使用 touch events 实现平滑滑动动画
 */
export default function SwipeableCard({
  children,
  actions = [],
  threshold = 60,
  className,
}: SwipeableCardProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isOpen, setIsOpen] = useState(false);

  const actionsWidth = actions.length * 72; // 每个操作按钮 72px

  useSwipe(containerRef, {
    onSwipeLeft: () => {
      if (actions.length > 0) setIsOpen(true);
    },
    onSwipeRight: () => {
      setIsOpen(false);
    },
    threshold,
  });

  const handleActionClick = (action: SwipeAction) => {
    setIsOpen(false);
    action.onClick();
  };

  return (
    <div
      ref={containerRef}
      className={cn('relative overflow-hidden rounded-lg touch-manipulation', className)}
    >
      {/* 操作按钮层（在卡片后面） */}
      {actions.length > 0 && (
        <div
          className="absolute inset-y-0 right-0 flex items-stretch"
          style={{ width: actionsWidth }}
        >
          {actions.map((action, index) => (
            <button
              key={index}
              onClick={() => handleActionClick(action)}
              className={cn(
                'flex flex-col items-center justify-center gap-1',
                'w-[72px] text-white text-xs font-medium',
                'min-h-[44px] touch-manipulation',
                'transition-opacity active:opacity-80',
                action.color ?? 'bg-destructive'
              )}
            >
              {action.icon && <span className="text-lg">{action.icon}</span>}
              <span>{action.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* 卡片内容层 */}
      <div
        className={cn(
          'relative bg-card border border-border rounded-lg',
          'transition-transform duration-300 ease-out'
        )}
        style={{
          transform: isOpen ? `translateX(-${actionsWidth}px)` : 'translateX(0)',
        }}
      >
        {children}
      </div>
    </div>
  );
}

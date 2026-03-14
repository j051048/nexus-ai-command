/**
 * 移动端 AI 半屏浮窗
 * 从底部滑出，支持半屏(60vh) ↔ 全屏(100dvh) 切换
 * 内嵌 EnhancedAIChatPanel
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { X, Minus, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import EnhancedAIChatPanel from '@/components/ai/EnhancedAIChatPanel';

type SheetState = 'closed' | 'half' | 'full';

interface MobileAISheetProps {
  isOpen: boolean;
  onClose: () => void;
  contextHint?: string;
}

export default function MobileAISheet({
  isOpen,
  onClose,
  contextHint,
}: MobileAISheetProps) {
  const [sheetState, setSheetState] = useState<SheetState>('closed');
  const dragStartY = useRef(0);
  const currentDragDelta = useRef(0);
  const sheetRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  // 同步外部 open 状态
  useEffect(() => {
    if (isOpen) {
      setSheetState('half');
    } else {
      setSheetState('closed');
    }
  }, [isOpen]);

  const handleClose = useCallback(() => {
    setSheetState('closed');
    setTimeout(onClose, 300); // 等动画完成
  }, [onClose]);

  const toggleFullscreen = useCallback(() => {
    setSheetState(prev => prev === 'full' ? 'half' : 'full');
  }, []);

  // 手势：拖拽把手上下拉
  const handleDragStart = useCallback((e: React.TouchEvent) => {
    e.stopPropagation();
    dragStartY.current = e.touches[0].clientY;
    currentDragDelta.current = 0;
    isDragging.current = true;
    // 开启 GPU 硬件加速
    if (sheetRef.current) {
      sheetRef.current.style.willChange = 'transform';
    }
  }, []);

  const handleDragMove = useCallback((e: React.TouchEvent) => {
    if (!isDragging.current) return;
    const delta = e.touches[0].clientY - dragStartY.current;
    currentDragDelta.current = delta;

    // 实时拖拽反馈
    if (sheetRef.current) {
      const clampedDelta = Math.max(0, delta); // 只允许向下拖
      sheetRef.current.style.transform = `translate3d(0, ${clampedDelta}px, 0)`;
      sheetRef.current.style.transition = 'none';
    }
  }, []);

  const handleDragEnd = useCallback(() => {
    if (!isDragging.current) return;
    isDragging.current = false;

    // 恢复 transition，清除 will-change
    if (sheetRef.current) {
      sheetRef.current.style.transform = '';
      sheetRef.current.style.transition = '';
      sheetRef.current.style.willChange = '';
    }

    const delta = currentDragDelta.current;

    if (delta > 100) {
      // 大幅下拉
      if (sheetState === 'full') {
        setSheetState('half');
      } else {
        handleClose();
      }
    } else if (delta < -80) {
      // 上拉
      if (sheetState === 'half') {
        setSheetState('full');
      }
    }
  }, [sheetState, handleClose]);

  const isVisible = sheetState !== 'closed';

  // 高度映射
  const heightClass = sheetState === 'full'
    ? 'h-[100dvh]'
    : sheetState === 'half'
      ? 'h-[60vh]'
      : 'h-0';

  return (
    <>
      {/* 遮罩层 */}
      {isVisible && (
        <div
          className={cn(
            'fixed inset-0 bg-black/20 z-[60] transition-opacity duration-300',
            isVisible ? 'opacity-100' : 'opacity-0 pointer-events-none'
          )}
          onClick={handleClose}
        />
      )}

      {/* 浮窗 */}
      <div
        ref={sheetRef}
        className={cn(
          'fixed left-0 right-0 bottom-0 z-[61]',
          'bg-background rounded-t-2xl shadow-2xl',
          'flex flex-col overflow-hidden',
          'transition-all duration-300 ease-out',
          heightClass,
          !isVisible && 'translate-y-full'
        )}
      >
        {/* 拖拽把手 + 标题栏 */}
        <div
          className="flex-shrink-0 touch-manipulation"
          onTouchStart={handleDragStart}
          onTouchMove={handleDragMove}
          onTouchEnd={handleDragEnd}
        >
          {/* 拖拽把手 */}
          <div className="flex justify-center py-2">
            <div className="w-10 h-1 bg-muted-foreground/30 rounded-full" />
          </div>

          {/* 标题栏 */}
          <div className="flex items-center justify-between px-4 pb-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-foreground">
                AI 助手
              </span>
              {contextHint && (
                <span className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded-full">
                  {contextHint}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={toggleFullscreen}
                aria-label={sheetState === 'full' ? '半屏' : '全屏'}
              >
                {sheetState === 'full' ? (
                  <Minus className="w-4 h-4" />
                ) : (
                  <Maximize2 className="w-4 h-4" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={handleClose}
                aria-label="关闭"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* AI Chat 内容 */}
        <div className="flex-1 overflow-hidden touch-manipulation">
          {isVisible && (
            <EnhancedAIChatPanel
              isExpanded={true}
              onToggle={() => {}}
              variant="embedded"
              compact={true}
            />
          )}
        </div>
      </div>
    </>
  );
}

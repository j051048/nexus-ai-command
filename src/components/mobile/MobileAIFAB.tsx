import { useRef } from 'react';
import { Bot, Mic } from 'lucide-react';

interface MobileAIFABProps {
  onClick: () => void;
  onLongPress?: () => void;
  visible?: boolean;
}

export default function MobileAIFAB({
  onClick,
  onLongPress,
  visible = true,
}: MobileAIFABProps) {
  const longPressTimer = useRef<number | null>(null);
  const didLongPress = useRef(false);

  if (!visible) return null;

  const clearLongPress = () => {
    if (longPressTimer.current) window.clearTimeout(longPressTimer.current);
    longPressTimer.current = null;
  };

  const handlePressStart = () => {
    didLongPress.current = false;
    if (!onLongPress) return;
    clearLongPress();
    longPressTimer.current = window.setTimeout(() => {
      didLongPress.current = true;
      onLongPress();
    }, 520);
  };

  const handleClick = () => {
    if (didLongPress.current) {
      didLongPress.current = false;
      return;
    }
    onClick();
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      onPointerDown={handlePressStart}
      onPointerUp={clearLongPress}
      onPointerCancel={clearLongPress}
      onPointerLeave={clearLongPress}
      className="fixed bottom-[calc(4.5rem+env(safe-area-inset-bottom))] right-4 z-40 flex h-11 w-11 touch-manipulation items-center justify-center rounded-md border border-primary/30 bg-primary text-primary-foreground shadow-md"
      aria-label="打开 AI 助手，长按语音速记"
    >
      <Bot className="h-4 w-4" />
      <Mic className="absolute -bottom-1 -right-1 h-4 w-4 rounded border bg-background p-0.5 text-primary" />
    </button>
  );
}

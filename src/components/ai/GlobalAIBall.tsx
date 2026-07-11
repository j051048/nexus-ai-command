import React, { useEffect } from 'react';
import { Bot } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface GlobalAIBallProps {
  isOpen: boolean;
  onClick: () => void;
  isProcessing?: boolean;
}

/** Compact assistant launcher. Alt+A remains the global keyboard shortcut. */
export const GlobalAIBall: React.FC<GlobalAIBallProps> = ({
  isOpen,
  onClick,
  isProcessing = false,
}) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.altKey && event.key.toLowerCase() === 'a') {
        event.preventDefault();
        onClick();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClick]);

  if (isOpen) return null;

  return (
    <TooltipProvider>
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={onClick}
            className="fixed bottom-5 left-5 z-[60] flex h-10 w-10 items-center justify-center rounded-md border border-primary/30 bg-primary text-primary-foreground shadow-md transition-colors hover:bg-primary/90"
            aria-label="打开企业助手"
          >
            <Bot className="h-4 w-4" />
            {isProcessing && (
              <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-background bg-warning" />
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">助手面板（Alt+A）</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

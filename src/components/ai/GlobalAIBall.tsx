import React, { useEffect, useState } from 'react';
import { Sparkles, Command } from 'lucide-react';
import { cn } from '@/lib/utils';
import { 
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface GlobalAIBallProps {
  isOpen: boolean;
  onClick: () => void;
  isProcessing?: boolean;
}

export const GlobalAIBall: React.FC<GlobalAIBallProps> = ({ 
  isOpen, 
  onClick, 
  isProcessing = false 
}) => {
  const [isHovered, setIsHovered] = useState(false);

  // Shortcut logic: Alt + A to toggle AI
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && e.key.toLowerCase() === 'a') {
        e.preventDefault();
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
            onClick={onClick}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            className={cn(
              "fixed bottom-8 left-8 z-[60] group",
              "w-14 h-14 rounded-2xl flex items-center justify-center transition-all duration-500",
              "bg-primary shadow-[0_8px_30px_rgb(var(--primary-rgb),0.3)] hover:shadow-[0_12px_40px_rgb(var(--primary-rgb),0.5)]",
              "active:scale-95 hover:scale-110",
              "border border-white/20 overflow-hidden"
            )}
          >
            {/* Background animated ring */}
            <div className={cn(
              "absolute inset-0 bg-gradient-to-tr from-white/20 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500",
              isProcessing && "animate-spin-slow opacity-30"
            )} />

            {/* Icon stack */}
            <div className="relative">
              <Sparkles 
                className={cn(
                  "w-7 h-7 text-white transition-all duration-300",
                  isHovered ? "scale-110 drop-shadow-[0_0_8px_rgba(255,255,255,0.8)]" : "scale-100",
                  isProcessing && "animate-pulse"
                )} 
              />
              
              {/* Notification dot if processing */}
              {isProcessing && (
                <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 border-2 border-primary rounded-full animate-ping" />
              )}
            </div>

            {/* Floating label on hover */}
            <div className={cn(
              "absolute left-full ml-4 px-3 py-1.5 bg-background/80 backdrop-blur-md border border-border rounded-lg text-[10px] font-bold text-foreground whitespace-nowrap opacity-0 translate-x-[-10px] transition-all duration-300 pointer-events-none",
              isHovered && "opacity-100 translate-x-0"
            )}>
              <div className="flex items-center gap-2">
                <span>打开助手</span>
                <div className="flex items-center gap-0.5 opacity-60 bg-muted px-1 rounded">
                  <Command className="w-2 h-2" />
                  <span>A</span>
                </div>
              </div>
            </div>

            {/* Shine effect */}
            <div className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right" className="bg-primary text-primary-foreground border-none font-bold">
          助手面板 (Alt+A)
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

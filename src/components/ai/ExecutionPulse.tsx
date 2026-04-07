import React from 'react';
import { motion } from 'framer-motion';
import { Loader2, CheckCircle2, ShieldCheck, Database, Search, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';

export type PulseType = 'thinking' | 'searching' | 'processing' | 'verifying' | 'writing';

interface ExecutionPulseProps {
  type: PulseType;
  label: string;
  sublabel?: string;
  isComplete?: boolean;
}

const pulseConfig: Record<PulseType, { icon: any, color: string, glow: string }> = {
  thinking: { icon: Zap, color: 'text-amber-500', glow: 'bg-amber-500/20' },
  searching: { icon: Search, color: 'text-blue-500', glow: 'bg-blue-500/20' },
  processing: { icon: Database, color: 'text-purple-500', glow: 'bg-purple-500/20' },
  verifying: { icon: ShieldCheck, color: 'text-emerald-500', glow: 'bg-emerald-500/20' },
  writing: { icon: CheckCircle2, color: 'text-indigo-500', glow: 'bg-indigo-500/20' },
};

export const ExecutionPulse: React.FC<ExecutionPulseProps> = ({ type, label, sublabel, isComplete }) => {
  const config = pulseConfig[type];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border bg-card/30 backdrop-blur-sm shadow-sm animate-in fade-in slide-in-from-left-2 transition-all">
      <div className="relative">
        <div className={cn("absolute inset-0 rounded-full blur-md animate-pulse", config.glow)} />
        <div className={cn(
          "relative flex h-8 w-8 items-center justify-center rounded-full border bg-background",
          isComplete ? "border-emerald-500/50" : "border-border"
        )}>
          {isComplete ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          ) : (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            >
              <Loader2 className="h-4 w-4 text-muted-foreground" />
            </motion.div>
          )}
          {!isComplete && (
            <div className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-75", config.glow.replace('20', '40'))}></span>
              <span className={cn("relative inline-flex rounded-full h-3 w-3", config.glow.replace('20', '100'))}></span>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col">
        <span className="text-xs font-bold text-foreground/90 flex items-center gap-1.5">
          <Icon className={cn("h-3 w-3", config.color)} />
          {label}
        </span>
        {sublabel && (
          <span className="text-[10px] text-muted-foreground tabular-nums">
            {sublabel}
          </span>
        )}
      </div>

      {!isComplete && (
        <div className="ml-auto pr-2">
           <div className="flex gap-0.5">
              {[0, 1, 2].map(i => (
                <motion.div
                  key={i}
                  className="h-1 w-1 rounded-full bg-primary/40"
                  animate={{ scale: [1, 1.5, 1], opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
                />
              ))}
           </div>
        </div>
      )}
    </div>
  );
};

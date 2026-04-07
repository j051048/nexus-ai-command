import React, { useState, useCallback } from 'react';
import { CheckCircle2, XCircle, Clock, CircleDot, Check, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { motion, AnimatePresence } from 'framer-motion';

interface ApprovalStep {
  id: string;
  name: string;
  status: 'pending' | 'approved' | 'rejected' | 'current';
  approver?: string;
  time?: string;
  canApprove?: boolean;
}

interface ApprovalFlowProps {
  steps: ApprovalStep[];
  title?: string;
  onSendMessage?: (prompt: string) => void;
  readOnly?: boolean;
}

const statusConfig = {
  approved: {
    icon: CheckCircle2,
    color: 'text-green-600 dark:text-green-400',
    bg: 'bg-green-50 dark:bg-green-950/30',
    border: 'border-green-200 dark:border-green-800',
    line: 'bg-green-400 dark:bg-green-600',
    label: '已通过',
  },
  rejected: {
    icon: XCircle,
    color: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-50 dark:bg-red-950/30',
    border: 'border-red-200 dark:border-red-800',
    line: 'bg-red-400 dark:bg-red-600',
    label: '已拒绝',
  },
  current: {
    icon: CircleDot,
    color: 'text-blue-600 dark:text-blue-400',
    bg: 'bg-blue-50 dark:bg-blue-950/30',
    border: 'border-blue-200 dark:border-blue-800',
    line: 'bg-blue-400 dark:bg-blue-600',
    label: '审批中',
  },
  pending: {
    icon: Clock,
    color: 'text-muted-foreground',
    bg: 'bg-muted/50',
    border: 'border-border',
    line: 'bg-border',
    label: '待审批',
  },
};

export default function ApprovalFlow({ steps: initialSteps, title, onSendMessage, readOnly = false }: ApprovalFlowProps) {
  const [steps, setSteps] = useState<ApprovalStep[]>(initialSteps);
  const [isProcessing, setIsProcessing] = useState<string | null>(null);

  const handleAction = useCallback(async (stepId: string, action: 'approve' | 'reject') => {
    if (isProcessing) return;
    
    setIsProcessing(stepId);
    
    // Simulate network delay for P3 "premium" feel
    await new Promise(resolve => setTimeout(resolve, 1200));

    setSteps(prev => prev.map(step => {
      if (step.id === stepId) {
        return { 
          ...step, 
          status: action === 'approve' ? 'approved' : 'rejected',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
      }
      // If approved, move to next step if it was pending
      return step;
    }));

    setIsProcessing(null);

    // Notify AI for context continuity
    if (onSendMessage) {
      onSendMessage(`我已${action === 'approve' ? '同意' : '决绝'}了「${steps.find(s => s.id === stepId)?.name}」的审批。`);
    }
  }, [isProcessing, onSendMessage, steps]);

  if (!steps?.length) return null;

  return (
    <div className="p-5 space-y-6">
      <div className="flex items-center justify-between">
        {title && <h4 className="text-sm font-bold tracking-tight text-foreground/90">{title}</h4>}
        <div className="flex items-center gap-2">
           <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
           <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">实时流程</span>
        </div>
      </div>

      <div className="relative space-y-1">
        {steps.map((step, i) => {
          const config = statusConfig[step.status];
          const Icon = config.icon;
          const isLast = i === steps.length - 1;
          const isActive = step.status === 'current';
          const canAction = step.canApprove && isActive && !readOnly;

          return (
            <motion.div 
              key={step.id} 
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
              className="group relative flex gap-4"
            >
              {/* Connector Line */}
              {!isLast && (
                <div 
                  className={cn(
                    "absolute left-[15px] top-[32px] w-[2px] h-[calc(100%-20px)] transition-colors duration-500",
                    config.line
                  )} 
                />
              )}

              {/* Status Icon */}
              <div className="relative z-10">
                <motion.div 
                  layoutId={`icon-${step.id}`}
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full border-2 transition-all duration-300 shadow-sm",
                    config.bg,
                    config.border,
                    isActive && "ring-4 ring-blue-500/10 scale-110"
                  )}
                >
                  <AnimatePresence mode="wait">
                    {isProcessing === step.id ? (
                      <motion.div
                        key="loader"
                        initial={{ opacity: 0, rotate: 0 }}
                        animate={{ opacity: 1, rotate: 360 }}
                        exit={{ opacity: 0 }}
                        transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                      >
                        <Loader2 className="h-4 w-4 text-blue-500" />
                      </motion.div>
                    ) : (
                      <motion.div
                        key="icon"
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1 }}
                      >
                        <Icon className={cn("h-4 w-4", config.color)} />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              </div>

              {/* Content Card */}
              <div className={cn(
                "flex-1 pb-8 transition-opacity",
                step.status === 'pending' && "opacity-60"
              )}>
                <div className="flex flex-col gap-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-foreground">{step.name}</span>
                    {step.time && <span className="text-[10px] text-muted-foreground">{step.time}</span>}
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded-full border", 
                      config.bg.replace('30', '10'), 
                      config.border,
                      config.color
                    )}>
                      {config.label}
                    </span>
                    {step.approver && (
                      <span className="text-[10px] text-muted-foreground">审批人: {step.approver}</span>
                    )}
                  </div>

                  {/* High-end Interaction Buttons */}
                  <AnimatePresence>
                    {canAction && (
                      <motion.div 
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="flex gap-2 mt-3 pt-2 border-t border-dashed border-border"
                      >
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs bg-green-500/5 hover:bg-green-500/10 border-green-500/20 text-green-600 dark:text-green-400 gap-1.5"
                          onClick={() => handleAction(step.id, 'approve')}
                          disabled={!!isProcessing}
                        >
                          <Check className="h-3 w-3" />
                          同意申请
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs bg-red-500/5 hover:bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-400 gap-1.5"
                          onClick={() => handleAction(step.id, 'reject')}
                          disabled={!!isProcessing}
                        >
                          <X className="h-3 w-3" />
                          驳回
                        </Button>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

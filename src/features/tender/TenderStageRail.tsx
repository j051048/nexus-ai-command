import { Check } from 'lucide-react';

import { cn } from '@/lib/utils';

import type { TenderStage } from './types';
import { TENDER_STAGE_DEFINITIONS } from './workspaceModel';

interface TenderStageRailProps {
  activeStage: TenderStage;
  onStageChange: (stage: TenderStage) => void;
  completedStages: TenderStage[];
}

export function TenderStageRail({ activeStage, onStageChange, completedStages }: TenderStageRailProps) {
  return (
    <nav aria-label="投标作业阶段" className="overflow-x-auto border-y bg-background/80">
      <div className="grid min-w-[720px] grid-cols-6">
        {TENDER_STAGE_DEFINITIONS.map((stage, index) => {
          const active = stage.id === activeStage;
          const completed = completedStages.includes(stage.id);
          return (
            <button
              key={stage.id}
              type="button"
              onClick={() => onStageChange(stage.id)}
              className={cn(
                'group relative flex min-h-16 items-center gap-3 border-r px-4 text-left transition-colors last:border-r-0 hover:bg-muted/50',
                active && 'bg-primary/[0.045]',
              )}
              aria-current={active ? 'step' : undefined}
            >
              <span
                className={cn(
                  'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs tabular-nums',
                  completed && 'border-emerald-600 bg-emerald-600 text-white',
                  active && !completed && 'border-primary bg-primary text-primary-foreground',
                )}
              >
                {completed ? <Check className="h-3.5 w-3.5" /> : index + 1}
              </span>
              <span className="min-w-0">
                <span className={cn('block text-sm font-medium', active ? 'text-foreground' : 'text-muted-foreground')}>
                  {stage.shortLabel}
                </span>
                <span className="block truncate text-xs text-muted-foreground">{stage.description}</span>
              </span>
              {active && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-primary" />}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

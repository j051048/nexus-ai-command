import { Check } from 'lucide-react';

import { cn } from '@/lib/utils';

export interface CompactStageDefinition<T extends string> {
  id: T;
  label: string;
  shortLabel: string;
  description: string;
}

interface CompactStageRailProps<T extends string> {
  label: string;
  stages: Array<CompactStageDefinition<T>>;
  activeStage: T;
  completedStages: T[];
  onStageChange: (stage: T) => void;
}

export function CompactStageRail<T extends string>({
  label,
  stages,
  activeStage,
  completedStages,
  onStageChange,
}: CompactStageRailProps<T>) {
  const activeDefinition = stages.find((stage) => stage.id === activeStage) ?? stages[0];

  return (
    <nav aria-label={label} className="border-y bg-background">
      <div className="overflow-x-auto">
        <ol className="flex min-w-[620px] items-center px-3 py-3">
          {stages.map((stage, index) => {
            const active = stage.id === activeStage;
            const completed = completedStages.includes(stage.id);
            return (
              <li key={stage.id} className="flex min-w-0 flex-1 items-center">
                <button
                  type="button"
                  onClick={() => onStageChange(stage.id)}
                  className={cn(
                    'group flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/50',
                    active && 'bg-primary/[0.055]',
                  )}
                  aria-current={active ? 'step' : undefined}
                  title={`${stage.label}：${stage.description}`}
                >
                  <span className={cn(
                    'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border bg-background text-[11px] tabular-nums text-muted-foreground',
                    completed && 'border-emerald-600 bg-emerald-600 text-white',
                    active && !completed && 'border-primary bg-primary text-primary-foreground',
                  )}>
                    {completed ? <Check className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  <span className={cn('truncate text-xs', active ? 'font-semibold text-foreground' : 'text-muted-foreground')}>{stage.shortLabel}</span>
                </button>
                {index < stages.length - 1 && <span className={cn('mx-1 h-px min-w-3 flex-1 bg-border', completed && 'bg-emerald-600/45')} aria-hidden="true" />}
              </li>
            );
          })}
        </ol>
      </div>
      {activeDefinition && (
        <div className="flex items-center gap-2 border-t bg-muted/20 px-4 py-2 text-xs">
          <span className="font-medium text-foreground">{activeDefinition.label}</span>
          <span className="text-muted-foreground">{activeDefinition.description}</span>
        </div>
      )}
    </nav>
  );
}

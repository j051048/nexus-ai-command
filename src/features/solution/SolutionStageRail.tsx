import { CompactStageRail } from '@/components/workflow/CompactStageRail';

import type { SolutionStage } from './types';
import { SOLUTION_STAGE_DEFINITIONS } from './workspaceModel';

interface SolutionStageRailProps {
  activeStage: SolutionStage;
  completedStages: SolutionStage[];
  onStageChange: (stage: SolutionStage) => void;
}

export function SolutionStageRail({ activeStage, completedStages, onStageChange }: SolutionStageRailProps) {
  return (
    <CompactStageRail label="方案作业阶段" stages={SOLUTION_STAGE_DEFINITIONS} activeStage={activeStage} completedStages={completedStages} onStageChange={onStageChange} />
  );
}

import { CompactStageRail } from '@/components/workflow/CompactStageRail';

import type { TenderStage } from './types';
import { TENDER_STAGE_DEFINITIONS } from './workspaceModel';

interface TenderStageRailProps {
  activeStage: TenderStage;
  onStageChange: (stage: TenderStage) => void;
  completedStages: TenderStage[];
}

export function TenderStageRail({ activeStage, onStageChange, completedStages }: TenderStageRailProps) {
  return (
    <CompactStageRail label="投标作业阶段" stages={TENDER_STAGE_DEFINITIONS} activeStage={activeStage} completedStages={completedStages} onStageChange={onStageChange} />
  );
}

import type {
  SolutionVersionSummary,
  SolutionWorkspaceState,
  SolutionStage,
} from './types';
import {
  BriefPanel,
  ConfigurationPanel,
  DeliveryPanel,
  DraftPanel,
  RequirementsPanel,
  ReviewPanel,
} from './SolutionStagePanels';

interface SolutionWorkspaceContentProps {
  stage: SolutionStage;
  projectId: string;
  workspace: SolutionWorkspaceState;
  versions?: SolutionVersionSummary[];
  onChange: (workspace: SolutionWorkspaceState) => void;
  onExport: (format: 'markdown' | 'docx' | 'pdf') => Promise<void>;
  onOutcome: (input: { outcome_type: 'proposal' | 'won' | 'lost' | 'revenue' | 'time_saved'; amount?: number; note?: string }) => Promise<void>;
  onPromoteTemplate: () => Promise<void>;
}

export function SolutionWorkspaceContent(props: SolutionWorkspaceContentProps) {
  const base = { workspace: props.workspace, onChange: props.onChange };
  if (props.stage === 'brief') return <BriefPanel {...base} />;
  if (props.stage === 'requirements') return <RequirementsPanel {...base} />;
  if (props.stage === 'configuration') return <ConfigurationPanel {...base} />;
  if (props.stage === 'draft') return <DraftPanel {...base} />;
  if (props.stage === 'review') return <ReviewPanel {...base} />;
  return <DeliveryPanel {...base} projectId={props.projectId} versions={props.versions} onExport={props.onExport} onOutcome={props.onOutcome} onPromoteTemplate={props.onPromoteTemplate} />;
}

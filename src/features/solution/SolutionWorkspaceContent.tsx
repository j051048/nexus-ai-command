import type {
  SolutionVersionSummary,
  SolutionWorkspaceState,
  SolutionStage,
  SolutionDocumentOption,
  SolutionProductOption,
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
  documents?: SolutionDocumentOption[];
  products?: SolutionProductOption[];
  isExtracting?: boolean;
  onChange: (workspace: SolutionWorkspaceState) => void;
  onExtract: (documentIds: string[]) => Promise<void>;
  onExport: (format: 'markdown' | 'docx' | 'pdf' | 'xlsx') => Promise<void>;
  onOutcome: (input: { outcome_type: 'proposal' | 'won' | 'lost' | 'revenue' | 'time_saved'; amount?: number; note?: string }) => Promise<void>;
  onPromoteTemplate: () => Promise<void>;
  onCreateTender: () => Promise<void>;
  onFeedback: (changeType: 'accepted' | 'edited' | 'rejected') => Promise<void>;
}

export function SolutionWorkspaceContent(props: SolutionWorkspaceContentProps) {
  const base = { workspace: props.workspace, onChange: props.onChange };
  if (props.stage === 'brief') return <BriefPanel {...base} />;
  if (props.stage === 'requirements') return <RequirementsPanel {...base} documents={props.documents} isExtracting={props.isExtracting} onExtract={props.onExtract} />;
  if (props.stage === 'configuration') return <ConfigurationPanel {...base} products={props.products} />;
  if (props.stage === 'draft') return <DraftPanel {...base} />;
  if (props.stage === 'review') return <ReviewPanel {...base} />;
  return <DeliveryPanel {...base} projectId={props.projectId} versions={props.versions} onExport={props.onExport} onOutcome={props.onOutcome} onPromoteTemplate={props.onPromoteTemplate} onCreateTender={props.onCreateTender} onFeedback={props.onFeedback} />;
}

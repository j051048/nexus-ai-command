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
  canManageCatalog?: boolean;
  canDeliver?: boolean;
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
  if (props.stage === 'configuration') return <ConfigurationPanel {...base} projectId={props.projectId} products={props.products} canManageCatalog={props.canManageCatalog} />;
  if (props.stage === 'draft') return <DraftPanel {...base} projectId={props.projectId} />;
  if (props.stage === 'review') return <ReviewPanel {...base} projectId={props.projectId} />;
  return <DeliveryPanel {...base} projectId={props.projectId} canDeliver={props.canDeliver} versions={props.versions} onExport={props.onExport} onOutcome={props.onOutcome} onPromoteTemplate={props.onPromoteTemplate} onCreateTender={props.onCreateTender} onFeedback={props.onFeedback} />;
}

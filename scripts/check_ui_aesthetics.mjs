import fs from 'node:fs';

const coreFiles = [
  'src/components/layout/ChatFirstLayout.tsx',
  'src/components/layout/Sidebar.tsx',
  'src/components/ai/GlobalAIBall.tsx',
  'src/components/ai/AIInsightPanel.tsx',
  'src/components/ai/chat/WorkflowStepper.tsx',
  'src/components/ai/chat/ChatHeader.tsx',
  'src/components/ai/chat/ChatInputArea.tsx',
  'src/components/ai/chat/CapabilityCards.tsx',
  'src/components/ai/chat/ChatSuggestions.tsx',
  'src/components/auth/LoginPage.tsx',
  'src/components/layout/MobileLayout.tsx',
  'src/components/mobile/MobileAIFAB.tsx',
  'src/components/mobile/MobilePageHeader.tsx',
  'src/components/mobile/MobileTabBar.tsx',
  'src/pages/InboxPage.tsx',
  'src/pages/crm/CRMPage.tsx',
  'src/components/approval/ApprovalCenter.tsx',
  'src/pages/ContractManagement.tsx',
  'src/pages/TenderAnalysisPage.tsx',
  'src/pages/AIOperatingSystemPage.tsx',
  'src/pages/AgentImprovementCenterPage.tsx',
  'src/components/agent-ops/AgentOpsOverview.tsx',
  'src/components/agent-ops/AgentOpsQuality.tsx',
  'src/components/agent-ops/AgentOpsReleases.tsx',
  'src/components/agent-ops/AgentOpsRuntime.tsx',
  'src/components/common/OperationalMetricStrip.tsx',
  'src/components/common/PrecisionPageHeader.tsx',
  'src/components/common/WelcomeTour.tsx',
  'src/components/common/WorkState.tsx',
  'src/components/deliverables/DeliverableCenter.tsx',
  'src/components/ui/badge.tsx',
  'src/components/ui/button.tsx',
  'src/components/ui/card.tsx',
  'src/components/ui/chart.tsx',
  'src/components/workflow/WorkflowCanvas.tsx',
  'src/components/workflow/WorkflowProperties.tsx',
  'src/components/workflow/WorkflowSidebar.tsx',
  'src/components/workflow/nodes/WorkflowNodeShell.tsx',
  'src/features/knowledge/KnowledgeAssetsPage.tsx',
  'src/features/solution/SolutionStagePanels.tsx',
  'src/pages/AgentDebugPanel.tsx',
  'src/pages/AgentRunsPage.tsx',
  'src/pages/SolutionWorkspacePage.tsx',
  'src/pages/WorkflowDesigner.tsx',
  'src/components/mobile/MobileWorkbenchPage.tsx',
];

const forbidden = [
  ['decorative gradient', /bg-gradient-(?:to|primary|cyber|card)/],
  ['glow effect', /(?:glow-|shadow-glow|text-shadow-glow)/],
  ['hover translation', /hover:-?translate-[xy]/],
  ['hover scaling', /hover:scale-/],
  ['decorative infinite animation', /animate-(?:blob|bounce|ping|glow)/],
  ['oversized radius', /rounded-(?:2xl|3xl)/],
  ['magic icon language', /(?:Sparkles|WandSparkles)/],
  ['generic all-property transition', /transition-all/],
  ['compressed letter spacing', /tracking-(?:tight|tighter)/],
];

const failures = [];
for (const file of coreFiles) {
  const source = fs.readFileSync(file, 'utf8');
  for (const [label, pattern] of forbidden) {
    if (pattern.test(source)) failures.push(`${file}: ${label}`);
  }
}

const designSystem = fs.readFileSync('src/index.css', 'utf8');
const tokenSource = fs.readFileSync('src/design-tokens/index.ts', 'utf8');
if (/--gradient-(?:primary|card|cyber):\s*linear-gradient/.test(designSystem)) {
  failures.push('src/index.css: active decorative gradient token');
}
if (/glow:\s*['"]0 0/.test(tokenSource)) {
  failures.push('src/design-tokens/index.ts: active glow shadow token');
}

if (failures.length) {
  console.error('UI_AESTHETICS_FAIL');
  failures.forEach((failure) => console.error(` - ${failure}`));
  process.exit(1);
}

console.log(`UI_AESTHETICS_OK (${coreFiles.length} core surfaces)`);

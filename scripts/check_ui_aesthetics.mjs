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
];

const forbidden = [
  ['decorative gradient', /bg-gradient-(?:to|primary|cyber|card)/],
  ['glow effect', /(?:glow-|shadow-glow|text-shadow-glow)/],
  ['hover translation', /hover:-?translate-[xy]/],
  ['hover scaling', /hover:scale-/],
  ['decorative infinite animation', /animate-(?:blob|bounce|ping|glow)/],
  ['oversized radius', /rounded-(?:2xl|3xl)/],
  ['magic icon language', /(?:Sparkles|WandSparkles)/],
];

const failures = [];
for (const file of coreFiles) {
  const source = fs.readFileSync(file, 'utf8');
  for (const [label, pattern] of forbidden) {
    if (pattern.test(source)) failures.push(`${file}: ${label}`);
  }
}

if (failures.length) {
  console.error('UI_AESTHETICS_FAIL');
  failures.forEach((failure) => console.error(` - ${failure}`));
  process.exit(1);
}

console.log(`UI_AESTHETICS_OK (${coreFiles.length} core surfaces)`);

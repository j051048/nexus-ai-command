#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const SOURCE_ROOTS = ["src"];
const EXTENSIONS = new Set([".js", ".jsx", ".ts", ".tsx"]);
const DEFAULT_MAX_LINES = 500;
const DEBT_GRACE_LINES = 25;

const IGNORED_DIRS = new Set([
  ".git",
  "coverage",
  "dist",
  "node_modules",
  "playwright-report",
  "test-results",
]);

const MANAGED_DEBT = new Map(
  Object.entries({
    "src/integrations/supabase/types.ts": 1298,
    "src/lib/i18n.ts": 1256,
    "src/pages/OACenter.tsx": 1248,
    "src/pages/LLMModelManagement.tsx": 1222,
    "src/lib/animations.ts": 1168,
    "src/pages/crm/CustomerDetailSheet.tsx": 1126,
    "src/hooks/useVMD.ts": 1035,
    "src/pages/OrgChartPage.tsx": 981,
    "src/pages/BattlecardLibrary.tsx": 933,
    "src/hooks/useAIStream.ts": 830,
    "src/pages/AgentDebugPanel.tsx": 816,
    "src/pages/FinanceCenter.tsx": 803,
    "src/pages/SuperAdminDashboard.tsx": 797,
    "src/pages/AdminPanel.tsx": 788,
    "src/pages/ContractManagement.tsx": 768,
    "src/pages/TenderAnalysisPage.tsx": 761,
    "src/pages/TrainingCenter.tsx": 731,
    "src/components/ai/MessageBubble.tsx": 722,
    "src/pages/NotificationCenter.tsx": 678,
    "src/components/common/EnhancedNotificationCenter.tsx": 652,
    "src/components/layout/GlobalCommandBar.tsx": 647,
    "src/pages/VMDTaskCenter.tsx": 646,
    "src/components/ui/sidebar.tsx": 638,
    "src/components/ai/chat/useChatPanel.ts": 629,
    "src/pages/HRCenter.tsx": 625,
    "src/components/projects/ProjectDetail.tsx": 622,
    "src/pages/VMDClueManagement.tsx": 620,
    "src/components/documents/DocumentsPage.tsx": 611,
    "src/components/approval/sections/BossApprovalView.tsx": 597,
    "src/components/common/DataExport.tsx": 591,
    "src/components/auth/LoginPage.tsx": 589,
    "src/components/settings/AISettingsPanel.tsx": 583,
    "src/pages/ProfileCenter.tsx": 582,
    "src/pages/AgentRunsPage.tsx": 573,
    "src/pages/AnimationShowcase.tsx": 569,
    "src/components/orgchart/OrgFlowCanvas.tsx": 557,
    "src/pages/InboxPage.tsx": 556,
    "src/components/workflow/WorkflowCanvas.tsx": 556,
    "src/components/layout/Sidebar.tsx": 550,
    "src/pages/AIOperatingSystemPage.tsx": 546,
    "src/pages/AgentImprovementCenterPage.tsx": 533,
    "src/components/onboarding/OnboardingWizard.tsx": 527,
    "src/pages/ReportBuilderPage.tsx": 525,
    "src/pages/DataImportPage.tsx": 521,
    "src/hooks/useAIOperatingSystem.ts": 520,
    "src/pages/APIKeysPage.tsx": 515,
    "src/components/common/AnimatedComponents.tsx": 512,
    "src/components/forms/DynamicFormRenderer.tsx": 510,
    "src/components/forms/FormFieldEditor.tsx": 502,
  }),
);

function normalizePath(filePath) {
  return path.relative(ROOT, filePath).split(path.sep).join("/");
}

function walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!IGNORED_DIRS.has(entry.name)) {
        walk(path.join(dir, entry.name), files);
      }
      continue;
    }
    if (entry.isFile() && EXTENSIONS.has(path.extname(entry.name))) {
      files.push(path.join(dir, entry.name));
    }
  }
  return files;
}

function countLines(filePath) {
  const content = fs.readFileSync(filePath, "utf8");
  if (!content) return 0;
  return content.split(/\r\n|\r|\n/).length;
}

const failures = [];
const warnings = [];

for (const sourceRoot of SOURCE_ROOTS) {
  const absoluteRoot = path.join(ROOT, sourceRoot);
  if (!fs.existsSync(absoluteRoot)) continue;

  for (const filePath of walk(absoluteRoot)) {
    const relativePath = normalizePath(filePath);
    const lines = countLines(filePath);
    const debtBaseline = MANAGED_DEBT.get(relativePath);

    if (debtBaseline !== undefined) {
      const allowed = debtBaseline + DEBT_GRACE_LINES;
      if (lines > allowed) {
        failures.push(
          `${relativePath}: ${lines} lines exceeds managed-debt cap ${allowed}`,
        );
      } else if (lines > DEFAULT_MAX_LINES) {
        warnings.push(`${relativePath}: ${lines} lines tracked as managed debt`);
      }
      continue;
    }

    if (lines > DEFAULT_MAX_LINES) {
      failures.push(
        `${relativePath}: ${lines} lines exceeds ${DEFAULT_MAX_LINES}; split into focused components/hooks`,
      );
    }
  }
}

if (warnings.length) {
  console.log("Source size managed-debt warnings:");
  for (const warning of warnings) console.log(` - ${warning}`);
}

if (failures.length) {
  console.error("SOURCE_SIZE_GATE_FAIL");
  for (const failure of failures) console.error(` - ${failure}`);
  process.exit(1);
}

console.log("SOURCE_SIZE_GATE_OK");

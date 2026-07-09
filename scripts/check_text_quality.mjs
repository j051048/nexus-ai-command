#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import path from 'node:path';

const root = process.cwd();

const defaultScope = [
  'src/components/ai/AIInsightPanel.tsx',
  'src/components/auth/RoleAccessHint.tsx',
  'src/components/common/EmptyState.tsx',
  'src/components/common/WorkState.tsx',
  'src/components/feedback/ExperienceFeedback.tsx',
  'src/components/mobile/MobileActionCardStack.tsx',
  'src/components/ai/chat/EnhancedAIChatPanel.tsx',
  'src/components/common/WelcomeTour.tsx',
  'src/components/dashboard/boss/TopPerformers.tsx',
  'src/components/layout/GlobalCommandBar.tsx',
  'src/components/product/AIOperatingSystemStrip.tsx',
  'src/components/sales/sections/PriorityLeads.tsx',
  'src/pages/AIOperatingSystemPage.tsx',
  'src/pages/InboxPage.tsx',
  'src/pages/TenderAnalysisPage.tsx',
];

const files = (process.env.TEXT_QUALITY_FILES || defaultScope.join(','))
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean);

const mojibakePatterns = [
  /�/,
  /锛|绠|鏃|鐨|寰|浠|杩|姝|鍙|琛|瀹|閫|灏|搴|鐢|妯|绋|浼|闂|浜/,
  /â€™|â€œ|â€|Ã©|Â/,
];

const forbiddenPlaceholders = [
  /TODO:\s*replace/i,
  /lorem ipsum/i,
  /示例文案待替换/,
  /占位文案/,
];

const forbiddenProductCopy = [
  { pattern: /AI\s*作战|作战系统|作战室/, message: 'uses war-room copy; prefer 工作台/助手/业务流' },
  { pattern: /销售指挥官|绩效教练|企业小助手/, message: 'uses over-personified agent names; prefer 销售助手/绩效助手/流程助手' },
  { pattern: /XP Score/, message: 'uses gamified score copy; prefer 绩效分/完成率' },
  { pattern: /立即突击/, message: 'uses aggressive action copy; prefer 立即联系/立即处理' },
  { pattern: /AI\s*证据链|优先级解释/, message: 'uses technical AI copy; prefer 参考依据/排序依据' },
  { pattern: /P0-P6/, message: 'exposes internal roadmap codes; prefer 本期重点/当前改进' },
];

let failures = 0;

for (const file of files) {
  const fullPath = path.join(root, file);
  const content = readFileSync(fullPath, 'utf8');
  const problems = [];

  if (mojibakePatterns.some((pattern) => pattern.test(content))) {
    problems.push('contains likely mojibake or replacement characters');
  }
  if (forbiddenPlaceholders.some((pattern) => pattern.test(content))) {
    problems.push('contains placeholder copy');
  }
  for (const rule of forbiddenProductCopy) {
    if (rule.pattern.test(content)) {
      problems.push(rule.message);
    }
  }

  if (problems.length > 0) {
    failures += 1;
    console.error(`FAIL ${file}: ${problems.join('; ')}`);
  } else {
    console.log(`OK   ${file}`);
  }
}

if (failures > 0) {
  console.error(`Text quality check failed for ${failures} file(s).`);
  process.exit(1);
}

console.log('Text quality check passed.');

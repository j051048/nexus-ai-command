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

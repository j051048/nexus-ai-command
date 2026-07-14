import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const root = process.cwd();

function source(relativePath: string) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

describe('manual membership approval UX guard', () => {
  it('keeps global billing notices free of recurring marketing prompts', () => {
    const banner = source('src/components/billing/TrialBanner.tsx');

    expect(banner).not.toContain('免费体验 14 天');
    expect(banner).not.toContain('立即体验');
    expect(banner).not.toContain('解锁全部 AI 能力');
    expect(banner).toContain("subscription.notice_policy !== 'action_required'");
  });

  it('uses one canonical super-admin console with progressive task tabs', () => {
    const admin = source('src/pages/AdminPanel.tsx');
    const compatibilityEntry = source('src/pages/SuperAdminDashboard.tsx');

    expect(admin).toContain('会员开通与续期');
    expect(admin).toContain('企业与会员');
    expect(admin).toContain('审计记录');
    expect(compatibilityEntry).toContain("export { default } from './AdminPanel'");
  });
});

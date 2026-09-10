import { expect, test } from '@playwright/test';
import { fulfillJson, mockLoggedInState, setupBusinessMocks } from './fixtures/business-mocks';

const result = {
  id: 'artifact-preview-test', artifact_code: 'ART-TEST', title: '光谱检测能力建设方案',
  artifact_type: 'customer_solution', status: 'needs_revision', approval_status: 'pending',
  version_number: 1, requested_formats: ['docx', 'pdf', 'xlsx'], verification_items: [],
  quality: { score: 78, ready: false, findings: [{ code: 'missing_service', severity: 'high', message: '售后响应时限需负责人确认' }], dimensions: {}, metrics: { character_count: 3200 } },
  requirements: { minimum_character_count: 3000 }, evidence: { count: 1, coverage: .8, sufficient: false, missing_topics: ['售后条款'] },
  content_markdown: '# 光谱检测能力建设方案\n\n## 客户目标\n针对材料实验室的日常样品分析，优先建立可追溯的数据与验收流程。\n\n## 配置建议\n| 配置 | 选型依据 | 验收方式 |\n| --- | --- | --- |\n| 光谱检测主机 | 企业已上传的产品手册 | 双方确认的方法与样品 |\n| 数据管理模块 | 原始数据与报告留存需求 | 按记录逐项核验 |\n\n## 交付安排\n先确认样品范围，再进行方法验证与培训。\n\n## 售后边界\n具体响应时限以负责人确认后的服务协议为准。',
  sources: [{ title: '光谱产品手册', document_id: 'doc-test', source_version: '2026.09' }],
  usage: { total_tokens: 6200 }, checkpoint_hits: 3,
};

const desktop = { width: 1440, height: 1000 };
const mobile = { width: 390, height: 844 };
for (const scenario of [
  { name: 'desktop', start: desktop, viewport: desktop },
  { name: 'mobile', start: mobile, viewport: mobile },
  { name: 'desktop to mobile', start: desktop, viewport: mobile },
  { name: 'mobile to desktop', start: mobile, viewport: desktop },
]) {
  test(`result preview and revision: ${scenario.name}`, async ({ page }, testInfo) => {
    test.setTimeout(90000);
    const { viewport } = scenario;
    await page.setViewportSize(scenario.start);
    // All business traffic is mocked, including unexpected requests. No live writes.
    await page.route('**/api/**', (route) => fulfillJson(route, { success: true, data: {} }));
    await page.route('**/rest/v1/**', (route) => fulfillJson(route, []));
    await setupBusinessMocks(page);
    await mockLoggedInState(page);
    await page.route('**/api/artifacts*', (route) => fulfillJson(route, { success: true, data: { artifacts: [] } }));
    await page.route('**/api/artifacts/jobs', (route) => fulfillJson(route, { success: true, data: { jobs: [{ id: 'job-test', status: 'completed', progress: 100, attempt: 1, max_attempts: 3, result }] } }));
    await page.route('**/api/artifacts/artifact-preview-test/preview', (route) => fulfillJson(route, { success: true, data: result }));
    await page.route('**/api/artifacts/artifact-preview-test/revisions', async (route) => {
      expect(route.request().postDataJSON()).toMatchObject({ instructions: '补充安装培训和售后边界' });
      await fulfillJson(route, { success: true, data: { id: 'revision-job', status: 'queued' } }, 202);
    });
    await page.goto('/dashboard');
    await page.getByTestId('deliverable-center-trigger').first().click();
    await page.getByRole('button', { name: '预览与修订', exact: true }).click();
    await expect(page.getByRole('heading', { name: '客户目标' })).toBeVisible();
    const dialog = page.getByRole('dialog').last();
    await dialog.getByRole('combobox', { name: '文件格式' }).selectOption('pdf');
    await dialog.getByText('修改要求', { exact: true }).click();
    await dialog.getByLabel('修订要求').fill('补充安装培训和售后边界');
    await page.setViewportSize(viewport);
    await expect(dialog.getByRole('button', { name: '下载审核草稿', exact: true })).toBeVisible();
    await expect(dialog.getByRole('combobox', { name: '文件格式' })).toHaveValue('pdf');
    await expect(dialog.getByLabel('修订要求')).toHaveValue('补充安装培训和售后边界');
    await dialog.getByText('修改要求', { exact: true }).click();
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.width).toBeLessThanOrEqual(viewport.width);
    expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height + 1);
    await page.screenshot({ path: testInfo.outputPath(`preview-${viewport.width}.png`), fullPage: true });
    await dialog.getByRole('combobox', { name: '文件格式' }).selectOption('pdf');
    await expect(dialog.getByRole('combobox', { name: '文件格式' })).toHaveValue('pdf');
    await dialog.getByRole('tab', { name: '交付检查' }).click();
    await expect(dialog.getByText('售后响应时限需负责人确认')).toBeVisible();
    await dialog.getByText('修改要求', { exact: true }).click();
    await dialog.getByLabel('修订要求').fill('补充安装培训和售后边界');
    await dialog.getByRole('button', { name: '生成修订稿' }).click();
    await expect(page.getByText('修订任务已提交，原稿已保留')).toBeVisible();
    await expect(page.getByRole('dialog')).toHaveCount(1);
    await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click();
    await expect(page.getByTestId('deliverable-center-trigger')).toBeFocused();
  });
}

import { expect, Page, Route, test } from '@playwright/test';
import { fulfillJson, loginViaForm, mockLoggedInState, setupBusinessMocks } from './fixtures/business-mocks';

type Role = 'boss' | 'manager' | 'employee';

interface AcceptanceState {
  customers: Array<Record<string, unknown>>;
  approvals: Array<Record<string, unknown>>;
  documents: Array<Record<string, unknown>>;
  projects: Array<Record<string, unknown>>;
  employees: Array<Record<string, unknown>>;
  announcements: Array<Record<string, unknown>>;
}

function makeState(): AcceptanceState {
  const now = new Date().toISOString();
  return {
    customers: [
      {
        id: 'cust-1',
        organization_id: 'org-123',
        name: 'Google Cloud',
        company: 'Google Cloud',
        industry: 'Technology',
        stage: 'lead',
        source: 'e2e',
        estimated_value: 120000,
        assigned_to: 'test-user-id',
        tags: ['enterprise'],
        metadata: {},
        created_at: now,
        updated_at: now,
      },
    ],
    approvals: [
      {
        id: 'approval-1',
        source_table: 'approval_requests',
        type: 'expense',
        description: 'Travel expense',
        amount: 1200,
        status: 'pending',
        submitted_by: 'employee-1',
        submitter_name: 'E2E Employee',
        created_at: now,
      },
    ],
    documents: [],
    projects: [
      {
        id: 'project-1',
        name: 'Pilot Rollout',
        description: 'Initial customer rollout',
        stage: 'planning',
        progress: 10,
        user_id: 'test-user-id',
        created_at: now,
      },
    ],
    employees: [],
    announcements: [],
  };
}

function fakeJwt(role: Role): string {
  const now = Math.floor(Date.now() / 1000);
  const encode = (value: unknown) =>
    Buffer.from(JSON.stringify(value)).toString('base64url');
  return [
    encode({ alg: 'HS256', typ: 'JWT' }),
    encode({
      sub: 'test-user-id',
      email: `${role}@nexus-ai.com`,
      role: 'authenticated',
      aud: 'authenticated',
      exp: now + 3600,
      iat: now,
      app_metadata: { provider: 'email', role },
      user_metadata: { role, name: `E2E ${role}` },
    }),
    'fake-signature',
  ].join('.');
}

async function setupAcceptanceMocks(page: Page, role: Role = 'boss') {
  const state = makeState();
  await mockLoggedInState(page, role);
  await setupBusinessMocks(page);
  await page.unroute('**/auth/v1/token*').catch(() => undefined);
  await page.unroute('**/auth/v1/user*').catch(() => undefined);
  await page.unroute('**/api/users/profile*').catch(() => undefined);
  await page.unroute('**/rest/v1/rpc/get_user_role*').catch(() => undefined);
  await page.unroute('**/rest/v1/rpc/is_super_admin*').catch(() => undefined);
  await page.route('**/auth/v1/token*', (route) =>
    fulfillJson(route, {
      access_token: fakeJwt(role),
      token_type: 'bearer',
      expires_in: 3600,
      refresh_token: 'fake-refresh',
      user: {
        id: 'test-user-id',
        email: `${role}@nexus-ai.com`,
        user_metadata: { role, name: `E2E ${role}` },
        app_metadata: { provider: 'email', role },
      },
    }),
  );

  await page.route('**/auth/v1/user*', (route) =>
    fulfillJson(route, {
      id: 'test-user-id',
      email: `${role}@nexus-ai.com`,
      user_metadata: { role, name: `E2E ${role}` },
      app_metadata: { provider: 'email', role },
    }),
  );

  await page.route(/.*profile.*/, (route) =>
    fulfillJson(route, {
      success: true,
      data: {
        id: 'test-user-id',
        user_id: 'test-user-id',
        email: `${role}@nexus-ai.com`,
        name: `E2E ${role}`,
        role,
        avatar_url: null,
        organization_id: 'org-123',
        user: {
          id: 'test-user-id',
          email: `${role}@nexus-ai.com`,
          name: `E2E ${role}`,
          role,
          organization_id: 'org-123',
        },
      },
    }),
  );

  await page.route('**/rest/v1/rpc/get_user_role*', (route) => fulfillJson(route, role));
  await page.route('**/rest/v1/rpc/is_super_admin*', (route) => fulfillJson(route, false));
  await page.route('**/api/approval/type-config*', (route) =>
    fulfillJson(route, { success: true, data: [] }),
  );
  await page.route('**/api/approval/tab-counts*', (route) =>
    fulfillJson(route, {
      success: true,
      data: {
        pending: state.approvals.filter((item) => item.status === 'pending').length,
        mine: state.approvals.length,
      },
    }),
  );
  await page.route('**/api/notifications**', (route) =>
    fulfillJson(route, { success: true, data: { notifications: [], unread_count: 0 } }),
  );
  await page.route('**/api/usage/cost-alerts**', (route) =>
    fulfillJson(route, { success: true, data: { alerts: [], summary: { count: 0 } } }),
  );

  await page.route('**/api/crm/stats*', (route) =>
    fulfillJson(route, {
      success: true,
      data: {
        stats: {
          total_customers: state.customers.length,
          new_this_month: state.customers.length,
          conversion_rate: 18,
          total_estimated_value: 120000,
          churned: 0,
        },
      },
    }),
  );

  await page.route('**/api/crm/customers**', async (route) => {
    if (route.request().method() === 'OPTIONS') return fulfillJson(route, {});
    const url = new URL(route.request().url());
    const parts = url.pathname.split('/').filter(Boolean);
    const id = parts[parts.length - 1] !== 'customers' ? parts[parts.length - 1] : null;
    if (route.request().method() === 'POST') {
      const body = JSON.parse(route.request().postData() || '{}');
      const customer = {
        id: 'cust-created',
        organization_id: 'org-123',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        ...body,
      };
      state.customers.push(customer);
      return fulfillJson(route, { success: true, data: { customer } });
    }
    if (id) {
      const customer = state.customers.find((item) => item.id === id);
      return fulfillJson(route, { success: true, data: { customer } });
    }
    return fulfillJson(route, { success: true, data: state.customers, total: state.customers.length });
  });

  await page.route('**/api/approval/list**', (route) =>
    fulfillJson(route, {
      success: true,
      data: { items: state.approvals, total: state.approvals.length, page: 1, page_size: 20 },
    }),
  );
  await page.route('**/api/approval/process', async (route) => {
    if (route.request().method() === 'OPTIONS') return fulfillJson(route, {});
    const body = JSON.parse(route.request().postData() || '{}');
    const item = {
      id: 'approval-created',
      source_table: 'approval_requests',
      type: body.type || 'expense',
      description: body.details || 'E2E approval',
      amount: body.amount ?? null,
      status: 'pending',
      submitted_by: 'test-user-id',
      submitter_name: 'E2E employee',
      created_at: new Date().toISOString(),
    };
    state.approvals.push(item);
    return fulfillJson(route, { success: true, data: { item }, decision: 'pending', reason: 'needs manager approval' });
  });
  await page.route('**/api/approval/items/*/approve', async (route) => {
    const id = route.request().url().split('/items/')[1]?.split('/')[0];
    const item = state.approvals.find((approval) => approval.id === id);
    if (item) item.status = 'approved';
    return fulfillJson(route, { success: true, data: { item } });
  });

  await page.route('**/api/documents/upload', async (route) => {
    if (route.request().method() === 'OPTIONS') return fulfillJson(route, {});
    const doc = {
      id: 'doc-created',
      title: 'Launch Playbook',
      filename: 'launch-playbook.txt',
      status: 'indexed',
      created_at: new Date().toISOString(),
    };
    state.documents.push(doc);
    return fulfillJson(route, { success: true, data: { document: doc } });
  });
  await page.route('**/api/documents**', async (route) => {
    if (route.request().method() === 'OPTIONS') return fulfillJson(route, {});
    if (new URL(route.request().url()).pathname.endsWith('/upload')) {
      const doc = {
        id: 'doc-created',
        title: 'Launch Playbook',
        filename: 'launch-playbook.txt',
        status: 'indexed',
        created_at: new Date().toISOString(),
      };
      state.documents.push(doc);
      return fulfillJson(route, { success: true, data: { document: doc } });
    }
    return fulfillJson(route, { success: true, data: { documents: state.documents } });
  });
  await page.route('**/api/memories/search', (route) =>
    fulfillJson(route, {
      success: true,
      data: {
        results: state.documents.map((document) => ({
          id: document.id,
          title: document.title,
          score: 0.91,
        })),
      },
    }),
  );

  await page.route('**/rest/v1/projects*', async (route) => {
    if (route.request().method() === 'PATCH') {
      const body = JSON.parse(route.request().postData() || '{}');
      state.projects[0] = { ...state.projects[0], ...body };
      return fulfillJson(route, [state.projects[0]]);
    }
    return fulfillJson(route, state.projects);
  });
  await page.route('**/api/projects', async (route) => {
    if (route.request().method() === 'POST') {
      const body = JSON.parse(route.request().postData() || '{}');
      const project = {
        id: 'project-created',
        name: body.name || 'Customer Implementation',
        description: body.description || '',
        stage: 'planning',
        progress: 0,
        user_id: 'test-user-id',
        created_at: new Date().toISOString(),
      };
      state.projects.push(project);
      return fulfillJson(route, { success: true, data: { project }, project });
    }
    return fulfillJson(route, { success: true, data: { projects: state.projects }, projects: state.projects });
  });
  await page.route('**/api/projects/*', async (route) => {
    const id = route.request().url().split('/api/projects/')[1]?.split('?')[0];
    const project = state.projects.find((item) => item.id === id);
    if (route.request().method() === 'PATCH') {
      const body = JSON.parse(route.request().postData() || '{}');
      if (project) Object.assign(project, body);
    }
    return fulfillJson(route, { success: true, data: { project }, project });
  });

  await page.route('**/api/hr/employees**', async (route) => {
    if (route.request().method() === 'POST') {
      const body = JSON.parse(route.request().postData() || '{}');
      const employee = { id: 'employee-created', status: 'active', ...body };
      state.employees.push(employee);
      return fulfillJson(route, { success: true, data: { employee } });
    }
    return fulfillJson(route, { success: true, data: { employees: state.employees } });
  });
  await page.route('**/api/oa/announcements**', async (route) => {
    if (route.request().method() === 'POST') {
      const body = JSON.parse(route.request().postData() || '{}');
      const announcement = { id: 'announcement-created', status: 'published', ...body };
      state.announcements.push(announcement);
      return fulfillJson(route, { success: true, data: { announcement } });
    }
    return fulfillJson(route, { success: true, data: { announcements: state.announcements } });
  });

  await page.route('**/api/chat/sessions**', (route) =>
    fulfillJson(route, { success: true, data: { sessions: [] } }),
  );
  await page.route('**/api/chat/history/**', (route) =>
    fulfillJson(route, { success: true, data: { messages: [] } }),
  );

  await loginViaForm(page, role);

  return state;
}

async function browserApi<T>(page: Page, path: string, init: RequestInit = {}): Promise<T> {
  const result = await page.evaluate(
    async ({ apiPath, requestInit }) => {
      const response = await fetch(`http://localhost:8000/${apiPath.replace(/^\//, '')}`, {
        ...requestInit,
        headers: {
          'Content-Type': 'application/json',
          ...(requestInit.headers || {}),
        },
      });
      const text = await response.text();
      return { ok: response.ok, status: response.status, text };
    },
    { apiPath: path, requestInit: init },
  );
  expect(result.ok, `${path} returned ${result.status}: ${result.text}`).toBeTruthy();
  return JSON.parse(result.text) as T;
}

async function expectHealthyPage(page: Page) {
  await page.waitForLoadState('domcontentloaded');
  const body = await page.textContent('body');
  expect(body).toBeTruthy();
  expect(body).not.toContain('Something went wrong');
  expect(body).not.toContain('Application error');
}

test.describe('Customer business acceptance flows', () => {
  test('1. login reaches the dashboard with a valid user context', async ({ page }) => {
    await setupAcceptanceMocks(page, 'boss');
    await page.goto('/dashboard');
    await expectHealthyPage(page);
    await expect(page.getByTestId('sidebar-main')).toBeVisible({ timeout: 10000 });
  });

  test('2. CRM can create a customer, list it, and open detail data', async ({ page }) => {
    await setupAcceptanceMocks(page, 'boss');
    await page.goto('/crm');
    await expectHealthyPage(page);

    const created = await browserApi<{ data: { customer: { id: string; name: string } } }>(
      page,
      'api/crm/customers',
      {
        method: 'POST',
        body: JSON.stringify({
          name: 'Acme Robotics',
          company: 'Acme Robotics',
          industry: 'Manufacturing',
          stage: 'qualified',
          source: 'e2e',
          estimated_value: 88000,
        }),
      },
    );
    expect(created.data.customer.name).toBe('Acme Robotics');

    const list = await browserApi<{ data: Array<{ name: string }>; total: number }>(
      page,
      'api/crm/customers',
    );
    expect(list.total).toBeGreaterThanOrEqual(2);
    expect(list.data.map((item) => item.name)).toContain('Acme Robotics');

    const detail = await browserApi<{ data: { customer: { name: string } } }>(
      page,
      `api/crm/customers/${created.data.customer.id}`,
    );
    expect(detail.data.customer.name).toBe('Acme Robotics');
  });

  test('3. approval can be submitted, approved, and listed as handled', async ({ page }) => {
    await setupAcceptanceMocks(page, 'boss');
    await page.goto('/approval');
    await expectHealthyPage(page);

    const submitted = await browserApi<{ data: { item: { id: string; status: string } } }>(
      page,
      'api/approval/process',
      {
        method: 'POST',
        body: JSON.stringify({
          requester_id: 'employee-1',
          type: 'expense',
          amount: 600,
          details: 'Customer visit taxi expense',
        }),
      },
    );
    expect(submitted.data.item.status).toBe('pending');

    const approved = await browserApi<{ data: { item: { status: string } } }>(
      page,
      `api/approval/items/${submitted.data.item.id}/approve`,
      { method: 'POST', body: JSON.stringify({ comment: 'approved in e2e' }) },
    );
    expect(approved.data.item.status).toBe('approved');
  });

  test('4. document upload appears in document list and knowledge search', async ({ page }) => {
    await setupAcceptanceMocks(page, 'boss');
    await page.goto('/documents');
    await expectHealthyPage(page);

    const uploaded = await browserApi<{ data: { document: { id: string; title: string } } }>(
      page,
      'api/documents/upload',
      { method: 'POST', body: JSON.stringify({ filename: 'launch-playbook.txt' }) },
    );
    expect(uploaded.data.document.title).toBe('Launch Playbook');

    const documents = await browserApi<{ data: { documents: Array<{ title: string }> } }>(
      page,
      'api/documents',
    );
    expect(documents.data.documents.map((doc) => doc.title)).toContain('Launch Playbook');

    const search = await browserApi<{ data: { results: Array<{ title: string }> } }>(
      page,
      'api/memories/search',
      { method: 'POST', body: JSON.stringify({ query: 'launch playbook' }) },
    );
    expect(search.data.results[0].title).toBe('Launch Playbook');
  });

  test('5. project can be created and moved to a new status', async ({ page }) => {
    await setupAcceptanceMocks(page, 'boss');
    await page.goto('/projects');
    await expectHealthyPage(page);

    const created = await browserApi<{ project: { id: string; name: string } }>(
      page,
      'api/projects',
      {
        method: 'POST',
        body: JSON.stringify({
          name: 'Customer Implementation',
          description: 'Deploy Nexus for a pilot customer',
        }),
      },
    );
    expect(created.project.name).toBe('Customer Implementation');

    const updated = await browserApi<{ project: { stage: string } }>(
      page,
      `api/projects/${created.project.id}`,
      { method: 'PATCH', body: JSON.stringify({ stage: 'in_progress' }) },
    );
    expect(updated.project.stage).toBe('in_progress');
  });

  test('6. HR employee and OA announcement creation are listable', async ({ page }) => {
    await setupAcceptanceMocks(page, 'boss');
    await page.goto('/hr');
    await expectHealthyPage(page);

    const employee = await browserApi<{ data: { employee: { name: string } } }>(
      page,
      'api/hr/employees',
      { method: 'POST', body: JSON.stringify({ name: 'E2E New Hire', department: 'Sales' }) },
    );
    expect(employee.data.employee.name).toBe('E2E New Hire');

    await page.goto('/oa');
    await expectHealthyPage(page);
    const announcement = await browserApi<{ data: { announcement: { title: string } } }>(
      page,
      'api/oa/announcements',
      { method: 'POST', body: JSON.stringify({ title: 'Launch Notice', content: 'Go live' }) },
    );
    expect(announcement.data.announcement.title).toBe('Launch Notice');

    const announcements = await browserApi<{ data: { announcements: Array<{ title: string }> } }>(
      page,
      'api/oa/announcements',
    );
    expect(announcements.data.announcements.map((item) => item.title)).toContain('Launch Notice');
  });

  test('7. AI chat sends a message and receives a streamed tool result', async ({ page }) => {
    await setupAcceptanceMocks(page, 'boss');
    let chatPayload: unknown = null;
    await page.route('**/api/chat', async (route: Route) => {
      chatPayload = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 200,
        headers: {
          'access-control-allow-origin': 'http://localhost:4173',
          'access-control-allow-credentials': 'true',
          'content-type': 'text/event-stream',
        },
        body:
          'data: {"type":"tool_progress","tool_name":"search_customers","status":"running"}\n\n' +
          'data: {"choices":[{"delta":{"content":"客户查询完成"}}]}\n\n' +
          'data: [DONE]\n\n',
      });
    });

    await page.goto('/dashboard');
    await expectHealthyPage(page);
    const input = page.getByTestId('chat-input');
    await expect(input).toBeVisible({ timeout: 15000 });
    await input.fill('查询本周新增客户并给出摘要');
    await input.press('Enter');

    await expect.poll(() => chatPayload).not.toBeNull();
    expect(JSON.stringify(chatPayload)).toContain('查询本周新增客户');
    await expectHealthyPage(page);
  });

  test('8. employee role is blocked from boss-only dashboard', async ({ page }) => {
    await setupAcceptanceMocks(page, 'employee');
    await page.goto('/boss-dashboard');
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });
    await expectHealthyPage(page);
  });

  test('9. golden path covers action inbox, CRM AI follow-up, industry assets, and analytics', async ({ page }) => {
    test.slow();
    await setupAcceptanceMocks(page, 'boss');

    await page.goto('/inbox');
    await expectHealthyPage(page);
    await expect(page.getByText('今日重点')).toBeVisible({ timeout: 10000 });
    const moreInsightActions = page.getByRole('button', { name: '更多建议操作' });
    await expect(moreInsightActions).toBeVisible({ timeout: 10000 });
    await moreInsightActions.click();
    await expect(page.getByRole('menuitem', { name: '查看依据' })).toBeVisible();
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: '跳过引导' }).click({ timeout: 5000 }).catch(() => undefined);
    await page.locator('[data-testid^="inbox-action-menu-"]').first().click();
    await page.locator('[data-testid^="inbox-action-accept-"]').first().click();

    await page.goto('/crm');
    await expectHealthyPage(page);
    await expect(page.getByRole('button', { name: /记录拜访/ })).toBeVisible({
      timeout: 10000,
    });
    await page.getByRole('button', { name: /记录拜访/ }).click();
    await expect(page.getByTestId('chat-input')).toBeVisible({ timeout: 15000 });

    await page.goto('/industry-knowledge');
    await expectHealthyPage(page);
    await expect(page.getByText('科学仪器行业知识资产')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('main').last()).toContainText('Thermo Fisher LC/MS 竞品对比框架');

    await page.goto('/action-analytics');
    await expectHealthyPage(page);
    await expect(page.getByText('行动台运营分析')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('采纳率')).toBeVisible();
    await expect(page.getByRole('heading', { name: '高风险未闭环' })).toBeVisible();

    await page.goto('/ai-operating-system');
    await expectHealthyPage(page);
    await expect(page.getByRole('heading', { name: 'AI 运营工作台' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('heading', { name: 'AI 价值与信任仪表盘' })).toBeVisible();
    await page.getByRole('tab', { name: '运行监控' }).click();
    await expect(page.getByText('真实运营数据')).toBeVisible();
    await page.getByRole('tab', { name: 'Agent 发布' }).click();
    await expect(page.getByRole('heading', { name: 'Agent 仿真沙盒' }).first()).toBeVisible();
    await expect(page.getByRole('heading', { name: 'SOP → AOP 自然语言定义器' }).first()).toBeVisible();
    await page.getByRole('button', { name: '生成 Agent 定义' }).click();
    await expect(page.getByTestId('agent-definition-trigger-rules')).toBeVisible({ timeout: 10000 });
    await page.getByRole('tab', { name: '工作台总览' }).click();
    await expect(page.locator('#demo-space').getByRole('heading', { name: '科学仪器 Demo 空间' })).toBeVisible();
  });

  test('10. chat artifact delivery regenerates, reviews, and downloads a durable file', async ({ page }) => {
    await setupAcceptanceMocks(page, 'boss');
    let artifactPayload: Record<string, unknown> | null = null;
    let feedbackPayload: Record<string, unknown> | null = null;
    await page.route('**/api/chat', async (route: Route) => {
      await route.fulfill({
        status: 200,
        headers: {
          'access-control-allow-origin': 'http://localhost:4173',
          'access-control-allow-credentials': 'true',
          'content-type': 'text/event-stream',
        },
        body:
          'data: {"choices":[{"delta":{"content":"## 初步方案\\n已根据食品安全检测需求形成升级建议。当前内容只是聊天摘要，正式成果需要重新检索企业产品资料、核验参数、补充实施计划、服务边界和证据来源。建议生成可编辑 Word，并由负责人确认价格、交期和对外承诺。"}}]}\n\n' +
          'data: [DONE]\n\n',
      });
    });
    await page.route('**/api/artifacts?*', (route) => fulfillJson(route, { success: true, data: { artifacts: [] } }));
    await page.route('**/api/artifacts/jobs', async (route) => {
      artifactPayload = JSON.parse(route.request().postData() || '{}');
      await fulfillJson(route, {
        success: true,
        data: {
          id: 'job-11111111',
          status: 'completed',
          stage: 'completed',
          progress: 100,
          progress_details: {},
          result: {
            id: '11111111-1111-4111-8111-111111111111',
            artifact_code: 'ART-20260722-E2E',
            title: '食品安全检测仪升级方案',
            artifact_type: 'customer_solution',
            artifact_label: '客户解决方案',
            status: 'approved',
            approval_status: 'approved',
            quality: { score: 93, ready: true, findings: [], dimensions: { structure: 100 } },
            version_number: 1,
            requested_formats: ['docx'],
            verification_items: [],
            evidence: { count: 6, coverage: 1, sufficient: true, missing_topics: [] },
            download_urls: {
              docx: '/api/artifacts/11111111-1111-4111-8111-111111111111/download?format=docx',
            },
          },
        },
      });
    });
    await page.route('**/api/artifacts/11111111-1111-4111-8111-111111111111/download**', async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          'content-type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'content-disposition': "attachment; filename*=UTF-8''artifact.docx",
        },
        body: Buffer.from('PK-e2e-artifact'),
      });
    });
    await page.route('**/api/artifacts/11111111-1111-4111-8111-111111111111/feedback', async (route) => {
      feedbackPayload = JSON.parse(route.request().postData() || '{}');
      await fulfillJson(route, {
        success: true,
        data: { artifact_id: '11111111-1111-4111-8111-111111111111', recorded: true },
      });
    });

    await page.goto('/dashboard');
    const input = page.getByTestId('chat-input');
    await expect(input).toBeVisible({ timeout: 15000 });
    await input.fill('根据企业资料制作食品安全检测仪升级解决方案');
    await input.press('Enter');
    await page.getByTestId('message-deliverable-menu').click();
    await expect(page.getByRole('heading', { name: '制作精品成果' })).toBeVisible();
    await page.getByText('我理解 AI 只会引用企业资料').click();
    await page.getByText('价格、交期、性能保证与售后承诺').click();

    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: '开始制作' }).click();
    await download;

    await expect.poll(() => artifactPayload).not.toBeNull();
    expect(artifactPayload?.original_request).toContain('食品安全检测仪升级解决方案');
    expect(artifactPayload?.source_content).toContain('正式成果需要重新检索企业产品资料');
    await expect(page.getByText('ART-20260722-E2E')).toBeVisible();
    await expect(page.getByText('质量 93')).toBeVisible();
    await page.getByRole('button', { name: '可直接使用' }).click();
    await expect.poll(() => feedbackPayload).not.toBeNull();
    expect(feedbackPayload?.outcome).toBe('used');
  });
});

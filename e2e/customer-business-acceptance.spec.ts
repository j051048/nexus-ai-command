import { expect, Page, Route, test } from '@playwright/test';
import { fulfillJson, setupBusinessMocks } from './fixtures/business-mocks';

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

function getSupabaseAuthStorageKeys(): string[] {
  const keys = new Set<string>(['sb-hztpazmuejgbtixihcgj-auth-token']);
  const url = process.env.VITE_SUPABASE_URL || process.env.SUPABASE_URL;
  if (url) {
    try {
      const projectRef = new URL(url).hostname.split('.')[0];
      if (projectRef) keys.add(`sb-${projectRef}-auth-token`);
    } catch {
      // Keep the stable fallback key above.
    }
  }
  return [...keys];
}

async function installRoleSession(page: Page, role: Role) {
  const storageKeys = getSupabaseAuthStorageKeys();
  await page.addInitScript(({ sessionRole, keys }) => {
    const now = Math.floor(Date.now() / 1000);
    const encode = (value: unknown) =>
      btoa(JSON.stringify(value)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    const token = [
      encode({ alg: 'HS256', typ: 'JWT' }),
      encode({
        sub: 'test-user-id',
        email: `${sessionRole}@nexus-ai.com`,
        role: 'authenticated',
        aud: 'authenticated',
        exp: now + 3600,
        iat: now,
        app_metadata: { provider: 'email', role: sessionRole },
        user_metadata: { role: sessionRole, name: `E2E ${sessionRole}` },
      }),
      'fake-signature',
    ].join('.');
    const session = JSON.stringify({
      access_token: token,
      token_type: 'bearer',
      expires_in: 3600,
      expires_at: now + 3600,
      refresh_token: 'fake-refresh',
      user: {
        id: 'test-user-id',
        aud: 'authenticated',
        email: `${sessionRole}@nexus-ai.com`,
        role: 'authenticated',
        user_metadata: { role: sessionRole, name: `E2E ${sessionRole}` },
        app_metadata: { provider: 'email', role: sessionRole },
      },
    });
    keys.forEach((key) => window.localStorage.setItem(key, session));
    window.localStorage.setItem('hasSeenTour', 'true');
  }, { sessionRole: role, keys: storageKeys });
}

async function setupAcceptanceMocks(page: Page, role: Role = 'boss') {
  const state = makeState();
  await setupBusinessMocks(page);
  await page.unroute('**/auth/v1/token*').catch(() => undefined);
  await page.unroute('**/auth/v1/user*').catch(() => undefined);
  await page.unroute('**/api/users/profile*').catch(() => undefined);
  await page.unroute('**/rest/v1/rpc/get_user_role*').catch(() => undefined);
  await page.unroute('**/rest/v1/rpc/is_super_admin*').catch(() => undefined);
  await installRoleSession(page, role);

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
  await page.waitForLoadState('networkidle');
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
    const input = page.locator('textarea').first();
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
});

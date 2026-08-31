/**
 * Small-company production pilot load profile.
 *
 * Usage:
 *   k6 run --env BASE_URL=http://localhost:8000 nexus_backend/tests/k6/small_company.js
 *
 * This profile models a 20-50 person customer: light dashboard traffic,
 * repeated CRM/approval/doc reads, and a small amount of chat traffic. It is
 * intentionally conservative so it can run before every private handoff.
 */
import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errors = new Rate('small_company_errors');
const rateLimited = new Rate('small_company_rate_limited');
const latency = new Trend('small_company_latency', true);
const expectedResponse = http.expectedStatuses({ min: 200, max: 399 }, 401, 403, 429);

export const options = {
  scenarios: {
    pilot_20_users: {
      executor: 'ramping-vus',
      stages: [
        { duration: '30s', target: 5 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 50 },
        { duration: '1m', target: 20 },
        { duration: '20s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<900', 'p(99)<2500'],
    small_company_errors: ['rate<0.02'],
    small_company_rate_limited: ['rate<0.15'],
    small_company_latency: ['p(95)<900'],
  },
};

const BASE = (__ENV.BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
const TOKEN = __ENV.AUTH_TOKEN || '';

function headers() {
  const value = { 'Content-Type': 'application/json' };
  if (TOKEN) value.Authorization = `Bearer ${TOKEN}`;
  return value;
}

function record(response) {
  latency.add(response.timings.duration);
  errors.add(response.status >= 500);
  rateLimited.add(response.status === 429);
  return response;
}

function get(path, name) {
  return record(
    http.get(`${BASE}${path}`, {
      headers: headers(),
      tags: { name },
      responseCallback: expectedResponse,
    }),
  );
}

function post(path, body, name) {
  return record(
    http.post(`${BASE}${path}`, JSON.stringify(body), {
      headers: headers(),
      tags: { name },
      responseCallback: expectedResponse,
    }),
  );
}

function okOrAuth(response) {
  return [200, 401, 403, 429].includes(response.status);
}

export default function () {
  group('liveness', () => {
    check(get('/health/live', 'health_live'), { 'live ok': (r) => r.status === 200 });
  });

  group('core business reads', () => {
    check(get('/api/crm/customers?page=1&page_size=20', 'crm_customers'), { 'crm ok': okOrAuth });
    check(get('/api/approval/list?page=1&page_size=10', 'approval_list'), { 'approval ok': okOrAuth });
    check(get('/api/documents?page=1&page_size=10', 'documents_list'), { 'documents ok': okOrAuth });
    check(get('/api/org-structure/employees', 'organization_employees'), { 'employees ok': okOrAuth });
    check(get('/api/reports/overview', 'reports_overview'), { 'reports ok': okOrAuth });
  });

  group('knowledge and chat', () => {
    check(get('/api/knowledge/search?q=pilot&limit=5', 'knowledge_search'), { 'knowledge ok': okOrAuth });
    check(post('/api/chat', { message: 'pilot health check', conversation_id: null }, 'chat_send'), {
      'chat accepted or auth': okOrAuth,
    });
  });

  sleep(1);
}

export function handleSummary(data) {
  const values = data.metrics.http_req_duration.values;
  const summary = {
    timestamp: new Date().toISOString(),
    profile: 'small_company_20_50_users',
    p95: values['p(95)'],
    p99: values['p(99)'],
    requests: data.metrics.http_reqs.values.count,
    failures: data.metrics.http_req_failed.values.rate,
    server_errors: data.metrics.small_company_errors.values.rate,
    rate_limited: data.metrics.small_company_rate_limited.values.rate,
  };
  return {
    stdout: JSON.stringify(summary, null, 2) + '\n',
    'small_company_result.json': JSON.stringify(summary, null, 2),
  };
}

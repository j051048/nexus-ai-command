/**
 * k6 性能基线测试
 * 用法: k6 run --env BASE_URL=http://localhost:8000 baseline.js
 *
 * 阈值:
 *   - p95 < 500ms (API 响应)
 *   - p99 < 1500ms
 *   - 错误率 < 1%
 */
import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ── Custom metrics ──
const errorRate = new Rate('errors');
const rateLimited = new Rate('rate_limited');
const apiDuration = new Trend('api_duration', true);
const expectedResponse = http.expectedStatuses({ min: 200, max: 399 }, 401, 403, 429);

// ── Options ──
export const options = {
  stages: [
    { duration: '30s', target: 10 },   // ramp up
    { duration: '1m',  target: 20 },   // steady
    { duration: '30s', target: 50 },   // spike
    { duration: '30s', target: 20 },   // recover
    { duration: '30s', target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1500'],
    errors: ['rate<0.01'],
    rate_limited: ['rate<0.20'],
  },
};

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const TOKEN = __ENV.AUTH_TOKEN || '';

function headers() {
  const h = { 'Content-Type': 'application/json' };
  if (TOKEN) h['Authorization'] = `Bearer ${TOKEN}`;
  return h;
}

function apiGet(path, tag) {
  const res = http.get(`${BASE}${path}`, {
    headers: headers(),
    tags: { name: tag },
    responseCallback: expectedResponse,
  });
  apiDuration.add(res.timings.duration);
  errorRate.add(res.status >= 500);
  rateLimited.add(res.status === 429);
  return res;
}

function apiPost(path, body, tag) {
  const res = http.post(`${BASE}${path}`, JSON.stringify(body), {
    headers: headers(),
    tags: { name: tag },
    responseCallback: expectedResponse,
  });
  apiDuration.add(res.timings.duration);
  errorRate.add(res.status >= 500);
  rateLimited.add(res.status === 429);
  return res;
}

function okOrProtected(response) {
  return [200, 401, 403, 429].includes(response.status);
}

// ── Scenarios ──
export default function () {
  group('Health & Meta', () => {
    const res = apiGet('/health/live', 'health');
    check(res, { 'health 200': (r) => r.status === 200 });
  });

  group('Billing Plans', () => {
    const res = apiGet('/api/billing/plans', 'billing_plans');
    check(res, {
      'plans 200': (r) => r.status === 200,
      'has plans': (r) => {
        try { return JSON.parse(r.body).data.plans.length > 0; } catch { return false; }
      },
    });
  });

  group('CRM Customers', () => {
    const res = apiGet('/api/crm/customers?page=1&page_size=10', 'crm_list');
    check(res, { 'crm available or protected': okOrProtected });
  });

  group('Chat Completion', () => {
    const res = apiPost('/api/chat', { message: '你好', conversation_id: null }, 'chat');
    check(res, { 'chat available or protected': okOrProtected });
  });

  group('Approval List', () => {
    const res = apiGet('/api/approval/list?page=1&page_size=5', 'approval_list');
    check(res, { 'approval available or protected': okOrProtected });
  });

  group('Knowledge Search', () => {
    const res = apiGet('/api/knowledge/search?q=test&limit=5', 'knowledge_search');
    check(res, { 'knowledge available or protected': okOrProtected });
  });

  group('Usage Stats', () => {
    const res = apiGet('/api/billing/usage', 'billing_usage');
    check(res, { 'usage available or protected': okOrProtected });
  });

  sleep(1);
}

// ── Summary ──
export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    p50: data.metrics.http_req_duration.values['p(50)'],
    p95: data.metrics.http_req_duration.values['p(95)'],
    p99: data.metrics.http_req_duration.values['p(99)'],
    error_rate: data.metrics.errors ? data.metrics.errors.values.rate : 0,
    rate_limited: data.metrics.rate_limited ? data.metrics.rate_limited.values.rate : 0,
    total_requests: data.metrics.http_reqs.values.count,
    rps: data.metrics.http_reqs.values.rate,
  };

  return {
    stdout: JSON.stringify(summary, null, 2) + '\n',
    'baseline_result.json': JSON.stringify(summary, null, 2),
  };
}

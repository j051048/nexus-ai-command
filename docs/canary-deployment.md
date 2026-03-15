# 金丝雀部署指南

> 从直接部署到生产环境迁移为金丝雀（Canary）发布策略。

## 1. 当前部署方式

```
开发者 Push → GitHub Actions CI → 构建 → 直接部署到生产
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              Vercel (前端)   Docker (后端)    Supabase (DB)
              自动部署        Zeabur 自动部署   手动迁移
```

**问题：**

- 每次部署直接影响 100% 用户
- 出问题只能事后回滚，用户已受影响
- 无法渐进验证新版本
- 数据库迁移无法灰度
- 缺少自动回滚机制

---

## 2. 目标架构

```
                              ┌─────────────────┐
                              │  流量管理器       │
                              │  (Cloudflare/    │
                              │   Zeabur/Vercel) │
                              └────────┬────────┘
                                       │
                          ┌────────────┼────────────┐
                          │ 95% 流量   │            │ 5% 流量
                    ┌─────▼─────┐           ┌──────▼──────┐
                    │  Stable    │           │   Canary    │
                    │  v1.2.3    │           │   v1.2.4    │
                    └───────────┘           └─────────────┘
                                                   │
                                            ┌──────▼──────┐
                                            │  监控 & 判定 │
                                            │  自动晋升/   │
                                            │  自动回滚    │
                                            └─────────────┘
```

---

## 3. Zeabur 后端金丝雀方案

### 3.1 方案：Zeabur 双服务 + Cloudflare 流量分割

Zeabur 原生不提供金丝雀部署，但可以通过以下方式实现：

**架构：**

```
Cloudflare (DNS + Workers)
  │
  ├── api.nexus-ai.com (主流量) → Zeabur Service "backend-stable"
  │
  └── api.nexus-ai.com (金丝雀) → Zeabur Service "backend-canary"
```

**实现步骤：**

**第 1 步：创建双服务**

在 Zeabur 项目中创建两个服务：
- `backend-stable` — 当前生产版本
- `backend-canary` — 新版本候选

两个服务共享相同的环境变量（通过 Zeabur Variables Group），但使用不同的 Docker image tag。

**第 2 步：Cloudflare Worker 流量分割**

```javascript
// cloudflare-worker: canary-router.js
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 决定路由目标
    const target = shouldRouteToCanary(request)
      ? env.CANARY_ORIGIN   // backend-canary.zeabur.app
      : env.STABLE_ORIGIN;  // backend-stable.zeabur.app

    // 添加标记 header
    const modifiedRequest = new Request(target + url.pathname + url.search, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });
    modifiedRequest.headers.set('X-Canary-Version', target === env.CANARY_ORIGIN ? 'canary' : 'stable');

    const response = await fetch(modifiedRequest);

    // 添加响应 header 用于调试
    const modifiedResponse = new Response(response.body, response);
    modifiedResponse.headers.set('X-Served-By', target === env.CANARY_ORIGIN ? 'canary' : 'stable');

    return modifiedResponse;
  }
};

function shouldRouteToCanary(request) {
  // 策略 1：基于 cookie（粘性会话）
  const cookie = request.headers.get('Cookie') || '';
  if (cookie.includes('canary=true')) return true;
  if (cookie.includes('canary=false')) return false;

  // 策略 2：基于百分比
  const canaryPercent = 5; // 5% 流量到金丝雀
  return Math.random() * 100 < canaryPercent;
}
```

**第 3 步：GitHub Actions 集成**

```yaml
# .github/workflows/canary-deploy.yml
name: Canary Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-canary:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build and push Docker image
        run: |
          docker build -t nexus-backend:canary .
          # Push to registry

      - name: Deploy to Zeabur (canary service)
        run: |
          # 使用 Zeabur CLI 部署到 backend-canary 服务
          zeabur deploy --service backend-canary

      - name: Set canary traffic to 5%
        run: |
          # 更新 Cloudflare Worker 的 canary 百分比
          curl -X PUT "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT/workers/scripts/canary-router/settings" \
            -H "Authorization: Bearer $CF_API_TOKEN" \
            -d '{"bindings": [{"name": "CANARY_PERCENT", "type": "plain_text", "text": "5"}]}'

      - name: Wait and monitor (10 minutes)
        run: |
          sleep 600
          # 检查金丝雀健康状态

      - name: Check canary health
        id: health-check
        run: |
          # 调用健康检查脚本
          python scripts/check_canary_health.py

      - name: Promote or rollback
        if: steps.health-check.outputs.healthy == 'true'
        run: |
          # 金丝雀通过 → 逐步提升流量
          # 5% → 25% → 50% → 100%
          echo "Canary passed! Promoting..."
```

### 3.2 替代方案：Zeabur 蓝绿部署

如果流量分割过于复杂，可以先用蓝绿部署：

```
1. 部署新版本到 backend-canary
2. 内部团队测试 backend-canary.zeabur.app
3. 测试通过 → 切换 DNS 到 canary
4. 老版本保留 30 分钟作为回滚备用
5. 确认无问题 → 删除老版本
```

---

## 4. Vercel 前端金丝雀方案

Vercel 原生支持 Preview Deployments 和 Skew Protection。

### 4.1 利用 Vercel 内置功能

**Preview Deployments：**
- 每个 PR 自动生成预览 URL
- 团队可在预览环境中验证

**Skew Protection：**
- Vercel 自动处理前后端版本不一致
- 旧客户端继续访问旧静态资源

**渐进式发布（需 Enterprise 计划）：**
- Vercel Edge Config + Feature Flags
- 按百分比逐步发布

### 4.2 低成本方案：Feature Flags

不依赖 Vercel Enterprise，通过 Feature Flags 实现前端灰度：

```typescript
// src/lib/featureFlags.ts
interface FeatureFlags {
  newDashboard: boolean;
  agUiProtocol: boolean;
  onboardingWizard: boolean;
}

export function getFeatureFlags(userId: string): FeatureFlags {
  // 从后端获取用户的 feature flags
  // 或基于用户 ID hash 决定
  const hash = simpleHash(userId) % 100;

  return {
    newDashboard: hash < 5,      // 5% 用户
    agUiProtocol: hash < 10,     // 10% 用户
    onboardingWizard: hash < 20, // 20% 用户
  };
}
```

---

## 5. 健康检查与晋升标准

### 5.1 金丝雀健康检查指标

| 指标 | 稳定版基线 | 金丝雀阈值 | 自动回滚触发 |
|------|-----------|-----------|-------------|
| 错误率 (5xx) | < 0.1% | < 0.5% | > 1% |
| P50 延迟 | < 200ms | < 300ms | > 500ms |
| P99 延迟 | < 2s | < 3s | > 5s |
| 健康检查 | 100% | > 99% | < 95% |
| 内存使用 | 基线 | < 基线 * 1.5 | > 基线 * 2 |
| Sentry 新错误 | 0 | < 3 | > 10 |

### 5.2 健康检查脚本

```python
# scripts/check_canary_health.py
import requests
import sys
import time

CANARY_URL = "https://backend-canary.zeabur.app"
STABLE_URL = "https://backend-stable.zeabur.app"
CHECK_INTERVAL = 30  # seconds
CHECK_DURATION = 600  # 10 minutes
ERROR_THRESHOLD = 0.01  # 1%
LATENCY_THRESHOLD_MS = 500

def check_health():
    errors = 0
    total = 0
    latencies = []

    start = time.time()
    while time.time() - start < CHECK_DURATION:
        total += 1
        try:
            resp = requests.get(f"{CANARY_URL}/api/health", timeout=5)
            latencies.append(resp.elapsed.total_seconds() * 1000)
            if resp.status_code != 200:
                errors += 1
        except Exception:
            errors += 1

        time.sleep(CHECK_INTERVAL)

    error_rate = errors / total if total > 0 else 1
    avg_latency = sum(latencies) / len(latencies) if latencies else 9999
    p99_latency = sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 9999

    print(f"Total checks: {total}")
    print(f"Error rate: {error_rate:.2%}")
    print(f"Avg latency: {avg_latency:.0f}ms")
    print(f"P99 latency: {p99_latency:.0f}ms")

    healthy = (
        error_rate < ERROR_THRESHOLD
        and avg_latency < LATENCY_THRESHOLD_MS
        and p99_latency < LATENCY_THRESHOLD_MS * 4
    )

    # GitHub Actions output
    print(f"::set-output name=healthy::{str(healthy).lower()}")
    return healthy

if __name__ == "__main__":
    if not check_health():
        print("CANARY FAILED - Triggering rollback")
        sys.exit(1)
    print("CANARY PASSED - Safe to promote")
```

### 5.3 晋升流程

```
              金丝雀部署
                  │
         ┌───────▼───────┐
         │  5% 流量       │  ← 10 分钟观察
         │  自动健康检查   │
         └───────┬───────┘
                 │ 通过
         ┌───────▼───────┐
         │  25% 流量      │  ← 15 分钟观察
         │  自动健康检查   │
         └───────┬───────┘
                 │ 通过
         ┌───────▼───────┐
         │  50% 流量      │  ← 15 分钟观察
         │  人工确认       │
         └───────┬───────┘
                 │ 确认
         ┌───────▼───────┐
         │  100% 流量     │  ← 金丝雀晋升为 stable
         │  旧版本降级    │
         └───────────────┘
```

---

## 6. 自动回滚触发器

### 6.1 回滚条件

任一条件满足即触发自动回滚：

1. **错误率飙升**：金丝雀 5xx 错误率 > 1%（持续 2 分钟）
2. **延迟恶化**：P99 延迟 > 5 秒（持续 3 分钟）
3. **健康检查失败**：`/api/health` 连续 3 次失败
4. **内存泄漏**：内存使用率持续上升超过基线 200%
5. **Sentry 告警**：10 分钟内新增 > 10 个不同错误

### 6.2 回滚流程

```
检测到异常
    │
    ▼
1. 立即将金丝雀流量降为 0%
2. 通知团队（Slack/飞书/企微）
3. 保留金丝雀实例用于调试
4. 记录回滚原因和指标
5. 生成事后分析报告模板
```

### 6.3 回滚实现

```yaml
# .github/workflows/canary-rollback.yml
name: Canary Rollback

on:
  workflow_dispatch:
    inputs:
      reason:
        description: 'Rollback reason'
        required: true

jobs:
  rollback:
    runs-on: ubuntu-latest
    steps:
      - name: Set canary traffic to 0%
        run: |
          curl -X PUT "$CF_WORKER_URL" \
            -d '{"canary_percent": 0}'

      - name: Notify team
        run: |
          curl -X POST "$WEBHOOK_URL" \
            -d "{\"text\": \"Canary rollback triggered: ${{ inputs.reason }}\"}"

      - name: Keep canary for debugging
        run: |
          echo "Canary service kept running for investigation"
          echo "Access: https://backend-canary.zeabur.app"
```

---

## 7. 监控仪表板需求

### 7.1 必要面板

| 面板 | 数据源 | 展示内容 |
|------|--------|----------|
| 流量分布 | Cloudflare Analytics | Stable vs Canary 请求量 |
| 错误率对比 | Sentry + 健康检查 | 两个版本的错误率曲线 |
| 延迟对比 | Cloudflare / APM | P50/P95/P99 延迟对比 |
| 资源使用 | Zeabur Metrics | CPU/Memory/Network |
| 部署时间线 | GitHub Actions | 部署历史 + 当前状态 |
| 回滚历史 | 自定义 | 历次回滚原因和时间 |

### 7.2 告警规则

| 告警 | 条件 | 通知渠道 | 自动动作 |
|------|------|----------|----------|
| Canary 高错误率 | 5xx > 1% 持续 2min | Slack + 飞书 | 自动回滚 |
| Canary 高延迟 | P99 > 5s 持续 3min | Slack | 自动回滚 |
| Canary 健康检查失败 | 连续 3 次失败 | Slack + 飞书 + 短信 | 自动回滚 |
| 晋升完成 | 金丝雀已晋升为 stable | Slack | 无 |
| 手动确认提醒 | 50% 阶段等待确认 | Slack | 无 |

---

## 8. 数据库迁移的特殊考虑

数据库迁移不能灰度，需要特殊处理：

### 8.1 向前兼容迁移

```
规则：新版本必须兼容旧 schema，旧版本必须兼容新 schema

示例 — 添加列：
  1. 先部署迁移（添加列，nullable，有默认值）
  2. 部署新代码（金丝雀）
  3. 新旧代码都能正常工作
  4. 金丝雀晋升后，再单独清理旧列

示例 — 删除列：
  1. 部署新代码（不再使用该列）
  2. 金丝雀晋升，确认所有实例都不用该列
  3. 部署迁移删除列
```

### 8.2 迁移流程

```
1. 数据库迁移先于代码部署
2. 迁移必须向前兼容
3. 金丝雀验证新代码 + 新 schema
4. 晋升后再执行破坏性 schema 变更
```

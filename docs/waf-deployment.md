# WAF 部署指南

> 为 Nexus AI Command 部署 Web Application Firewall (WAF)。

## 1. 推荐方案：Cloudflare WAF

### 为什么选择 Cloudflare

| 考量 | Cloudflare | AWS WAF | 自建 ModSecurity |
|------|------------|---------|-------------------|
| 与 Zeabur 集成 | DNS 代理即可 | 需要 ALB | 需要自建反向代理 |
| 部署复杂度 | 低（改 DNS） | 中 | 高 |
| 免费层 | 有（含基础规则） | 无 | 开源免费 |
| DDoS 防护 | 内置 | 需额外配置 | 需另外部署 |
| Bot 防护 | 内置 | 需另购 | 需另外部署 |
| 全球边缘节点 | 300+ 节点 | 按区域 | 单点 |
| 维护成本 | 低（SaaS） | 中 | 高 |

---

## 2. Cloudflare WAF 部署步骤

### 2.1 DNS 配置

**第 1 步：添加域名到 Cloudflare**

1. 登录 Cloudflare Dashboard
2. Add Site → 输入域名（如 `nexus-ai.com`）
3. 选择计划：
   - Free：基础 WAF 规则（Managed Ruleset 有限子集）
   - Pro ($20/mo)：完整 WAF + 5 条自定义规则
   - Business ($200/mo)：高级 WAF + 自定义规则集 + Bot Management
   - 推荐：**Pro** 作为起步

**第 2 步：更新 DNS 记录**

```
Type    Name    Content                         Proxy
CNAME   api     your-backend.zeabur.app         Proxied (橙色云)
CNAME   @       your-frontend.vercel.app        Proxied (橙色云)
```

> 确保云朵图标为橙色（Proxied），灰色（DNS Only）不经过 WAF。

**第 3 步：SSL/TLS 配置**

- SSL/TLS → Overview → 选择 "Full (Strict)"
- Edge Certificates → Always Use HTTPS → On
- Minimum TLS Version → TLS 1.2

### 2.2 启用 WAF Managed Rulesets

路径：Security → WAF → Managed rules

**启用以下规则集：**

1. **Cloudflare Managed Ruleset** → 启用
   - 覆盖常见攻击向量
   - 默认 action: Block

2. **Cloudflare OWASP Core Rule Set** → 启用
   - 基于 OWASP CRS 3.x
   - 默认 action: Block
   - Paranoia Level: 建议从 PL1 开始，观察后逐步提高

3. **Cloudflare Leaked Credentials Detection** → 启用
   - 检测已泄露的凭证对

---

## 3. API 保护自定义规则

### 3.1 API 端点限制

路径：Security → WAF → Custom rules

**规则 1：阻止非法 HTTP 方法**

```
名称: Block non-standard methods for API
匹配条件:
  (http.request.uri.path contains "/api/")
  AND
  (not http.request.method in {"GET" "POST" "PUT" "PATCH" "DELETE" "OPTIONS"})
动作: Block
```

**规则 2：阻止无认证的敏感端点访问**

```
名称: Require auth header on protected endpoints
匹配条件:
  (http.request.uri.path contains "/api/")
  AND
  (not http.request.uri.path contains "/api/health")
  AND
  (not http.request.uri.path contains "/api/auth/")
  AND
  (not http.request.headers["authorization"][0] contains "Bearer ")
  AND
  (not http.request.headers["x-api-key"][0] ne "")
  AND
  (http.request.method ne "OPTIONS")
动作: Block (403)
```

**规则 3：保护管理端点**

```
名称: Admin endpoint IP restriction
匹配条件:
  (http.request.uri.path contains "/api/admin/")
  AND
  (not ip.src in {办公室IP/32 VPN出口IP/32})
动作: Block
```

**规则 4：阻止 SQL 注入探测（增强）**

```
名称: Block SQL injection patterns
匹配条件:
  (http.request.uri.query contains "UNION" and http.request.uri.query contains "SELECT")
  OR
  (http.request.uri.query contains "' OR '1'='1")
  OR
  (http.request.uri.query contains "DROP TABLE")
  OR
  (http.request.uri.query contains "INFORMATION_SCHEMA")
动作: Block + Challenge
```

**规则 5：限制请求体大小**

```
名称: Block oversized request bodies
匹配条件:
  (http.request.body.size gt 52428800)
  AND
  (not http.request.uri.path contains "/api/documents/upload")
动作: Block
注: 文件上传端点允许 50MB，其他端点默认限制
```

---

## 4. 速率限制（WAF 层）

路径：Security → WAF → Rate limiting rules

### 4.1 全局 API 速率限制

```
名称: Global API rate limit
匹配条件:
  (http.request.uri.path contains "/api/")
速率: 300 requests per 1 minute
分组依据: ip.src
动作: Block for 60 seconds
```

### 4.2 认证端点限制（防暴力破解）

```
名称: Auth endpoint rate limit
匹配条件:
  (http.request.uri.path contains "/api/auth/login")
  OR
  (http.request.uri.path contains "/api/auth/token")
速率: 10 requests per 1 minute
分组依据: ip.src
动作: Challenge for 300 seconds
```

### 4.3 AI Chat 限制（防滥用/防高成本）

```
名称: AI chat rate limit
匹配条件:
  (http.request.uri.path contains "/api/agent/chat")
速率: 20 requests per 1 minute
分组依据: ip.src
动作: Block for 120 seconds
```

### 4.4 文件上传限制

```
名称: File upload rate limit
匹配条件:
  (http.request.uri.path contains "/api/documents/upload")
速率: 10 requests per 1 minute
分组依据: ip.src
动作: Block for 300 seconds
```

### 与应用层限流的关系

```
              请求流量
                │
    ┌───────────▼───────────┐
    │   Cloudflare WAF      │  ← 第一层：粗粒度，按 IP
    │   Rate Limit: 300/min │     阻挡 DDoS + 暴力扫描
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │   应用层 Rate Limit   │  ← 第二层：细粒度，按用户/租户
    │   60/min per user     │     业务级限流 + 配额控制
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │   业务逻辑             │
    └───────────────────────┘
```

---

## 5. Bot 防护配置

路径：Security → Bots

### 5.1 Bot Fight Mode（Free 计划可用）

- 启用 Bot Fight Mode → On
- 自动挑战已知恶意 bot

### 5.2 Super Bot Fight Mode（Pro 计划）

```
Definitely automated    → Block
Likely automated        → Managed Challenge
Likely human           → Allow
Verified bots          → Allow (Google, Bing 等搜索引擎)
```

### 5.3 已验证 Bot 白名单

允许以下合法 bot 访问前端：
- Googlebot
- Bingbot
- Monitoring services (UptimeRobot, Pingdom)

API 端点 (`/api/`) 应对所有 bot 生效速率限制。

---

## 6. OWASP Core Rule Set 配置

### 6.1 Paranoia Level 建议

| 阶段 | Paranoia Level | 持续时间 | 说明 |
|------|---------------|----------|------|
| 部署初期 | PL1 | 2 周 | 最宽松，仅检测明显攻击 |
| 观察期 | PL1 + 特定 PL2 规则 | 2 周 | 启用部分 PL2 规则 |
| 稳定期 | PL2 | 长期 | 平衡安全和误报 |
| 高安全需求 | PL3 | 评估后 | 更严格，可能增加误报 |

### 6.2 需要例外的规则

以下场景可能触发误报，需配置例外：

**AI Chat 端点：**
- 用户消息可能包含代码片段 → 触发 SQL/XSS 规则
- 解决方案：为 `/api/agent/chat` 的请求体排除 920xxx 和 941xxx 规则组

```
规则例外:
  匹配: http.request.uri.path eq "/api/agent/chat"
  跳过规则: 920xxx (Protocol Attack), 941xxx (XSS)
  保留规则: 942xxx (SQL Injection), 949xxx (Blocking Evaluation)
```

**文件上传端点：**
- 二进制文件内容会触发规则
- 解决方案：为上传端点排除请求体检查

**Webhook 回调端点：**
- 第三方平台（飞书/企微/钉钉）的回调格式可能触发规则
- 解决方案：为 `/api/im/callback/*` 配置例外

### 6.3 监控和调优

部署后持续监控：

1. **Security → Events**：查看被阻止的请求
2. **Analytics → Security**：查看攻击趋势
3. 每周审查误报，调整规则例外
4. 每月审查安全事件报告

---

## 7. 部署清单

### 部署前

- [ ] 备份当前 DNS 配置
- [ ] 通知团队 WAF 部署时间窗口
- [ ] 准备回滚方案（将 DNS 改回 DNS Only）
- [ ] 列出所有需要白名单的 IP/服务

### 部署中

- [ ] 添加域名到 Cloudflare
- [ ] 更新 DNS 记录（设为 Proxied）
- [ ] 配置 SSL/TLS 为 Full (Strict)
- [ ] 启用 Managed Rulesets（先 Log Only 模式）
- [ ] 配置自定义规则
- [ ] 配置速率限制
- [ ] 启用 Bot 防护
- [ ] 验证所有端点正常工作
- [ ] 切换 Managed Rulesets 为 Block 模式

### 部署后

- [ ] 监控 72 小时内的误报
- [ ] 调整规则例外
- [ ] 验证合法请求不受影响
- [ ] 确认 WebSocket 连接正常（`/ws` 端点）
- [ ] 文档化最终配置
- [ ] 设置月度安全审查日历

### 回滚方案

如果 WAF 造成严重问题：

1. 将 DNS 代理状态改为 "DNS Only"（灰色云朵）
2. 流量将直接到达 Zeabur/Vercel，绕过 Cloudflare
3. 排查问题后重新启用

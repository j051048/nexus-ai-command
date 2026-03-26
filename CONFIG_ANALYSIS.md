# Nexus 未启用功能配置分析报告

## 📊 配置状态总览

基于 `config.py` 定义与 `.env` 实际配置的对比分析。

---

## ✅ 已配置项

- ✅ Supabase (数据库)
- ✅ OpenAI API (主 AI 服务)
- ✅ AI Fallback (备用 AI)
- ✅ APISpace 招投标
- ✅ JWT Secret
- ✅ TurboQuant (刚启用)

---

## ⚠️ 未配置但已实现的功能

### 🔴 P0 级（影响核心功能）

#### 1. 联网搜索 (Web Search)
**缺失**: `BRAVE_SEARCH_API_KEY`
**影响**: Agent 无法实时获取互联网信息
**获取方式**: https://brave.com/search/api/
**成本**: 免费额度 2000 次/月

#### 2. 敏感数据加密
**缺失**: `ENCRYPTION_KEY`
**影响**: 用户 API Key 无法加密存储（安全隐患）
**生成方式**:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

### 🟡 P1 级（影响生产体验）

#### 3. 多渠道通知
**缺失**:
- `SMTP_PASSWORD` (邮件)
- `DINGTALK_WEBHOOK_URL` (钉钉)
- `FEISHU_WEBHOOK_URL` (飞书)
- `WECOM_WEBHOOK_URL` (企微)

**影响**: Agent 完成任务后无法通知用户
**推荐**: 至少配置一个通知渠道

#### 4. LLM 可观测性
**缺失**:
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`

**影响**: 无法追踪 Token 成本和性能
**获取方式**: https://cloud.langfuse.com (免费)

#### 5. 异常监控
**缺失**: `SENTRY_DSN`
**影响**: 线上崩溃无法实时报警
**获取方式**: https://sentry.io (免费额度)

#### 6. 高精度重排序
**缺失**: `COHERE_API_KEY`
**影响**: 检索准确率降低 5-8%
**获取方式**: https://cohere.com (免费试用)
**备注**: 当前使用 LLM 重排序（较慢）

---

### 🟢 P2 级（商业化功能）

#### 7. 支付系统
**缺失**:
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_*`

**影响**: 付费订阅功能无法使用
**备注**: 仅在商业化时需要

---

## 🎯 推荐配置优先级

### 立即配置（5 分钟）
1. ✅ `ENCRYPTION_KEY` - 生成并添加（安全必需）
2. ✅ `BRAVE_SEARCH_API_KEY` - 免费注册（核心能力）

### 本周配置（1 小时）
3. `DINGTALK_WEBHOOK_URL` 或 `FEISHU_WEBHOOK_URL` - 选一个
4. `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` - 免费
5. `SENTRY_DSN` - 免费

### 按需配置
6. `COHERE_API_KEY` - 如需提升检索精度
7. Stripe 相关 - 商业化时配置

---

## 📝 配置模板

将以下内容添加到 `nexus_backend/.env`:

```bash
# ── P0: 安全与核心能力 ──────────────────────────────────────────────
# 敏感数据加密（必需）
ENCRYPTION_KEY=<运行上面的 Python 命令生成>

# 联网搜索（推荐）
BRAVE_SEARCH_API_KEY=<从 brave.com/search/api 获取>

# ── P1: 生产环境观测 ──────────────────────────────────────────────
# LLM 可观测性
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=<从 cloud.langfuse.com 获取>
LANGFUSE_SECRET_KEY=<从 cloud.langfuse.com 获取>

# 异常监控
SENTRY_DSN=<从 sentry.io 获取>

# ── P1: 通知渠道（选一个） ──────────────────────────────────────────
# 钉钉 Webhook
DINGTALK_WEBHOOK_URL=<从钉钉群机器人获取>

# 或飞书 Webhook
FEISHU_WEBHOOK_URL=<从飞书群机器人获取>

# ── P1: 高精度检索（可选） ──────────────────────────────────────────
COHERE_API_KEY=<从 cohere.com 获取>
RERANKER_BACKEND=cohere
```

---

## ⚡ 快速启用脚本

我可以帮你：
1. 生成 `ENCRYPTION_KEY`
2. 创建配置模板
3. 验证配置是否生效

需要我现在执行吗？

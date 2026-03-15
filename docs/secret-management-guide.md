# Secret Management 迁移指南

> 目标：将 Nexus AI Command 从明文 `.env` 文件管理密钥迁移到集中化的密钥管理服务。

## 1. 当前状态

### 当前方案：`.env` 文件明文存储

```
nexus_backend/.env          # 后端密钥
.env                        # 前端环境变量
```

**存在的风险：**

| 风险 | 严重程度 | 说明 |
|------|----------|------|
| 密钥泄露 | 严重 | `.env` 文件可能被误提交到 Git |
| 无审计日志 | 高 | 无法追踪谁在何时访问了哪个密钥 |
| 无轮换机制 | 高 | 密钥长期不变，泄露窗口大 |
| 环境不隔离 | 中 | 开发/测试/生产密钥管理方式相同 |
| 无访问控制 | 中 | 任何有服务器访问权限的人都能看到所有密钥 |

---

## 2. 需迁移的密钥清单

### 关键级别（Critical）— 泄露即灾难

| 密钥 | 当前位置 | 用途 | 轮换建议 |
|------|----------|------|----------|
| `SUPABASE_SERVICE_KEY` | `.env` | 绕过 RLS 的管理员密钥 | 90 天 |
| `SUPABASE_JWT_SECRET` | `.env` | JWT 签名验证 | 180 天 |
| `OPENAI_API_KEY` | `.env` | AI 服务主密钥 | 90 天 |
| `AI_FALLBACK_API_KEY` | `.env` | AI 备用服务密钥 | 90 天 |

### 高级别（High）— 泄露可造成经济损失或数据泄露

| 密钥 | 当前位置 | 用途 | 轮换建议 |
|------|----------|------|----------|
| `REDIS_URL` | `.env` | 含密码的 Redis 连接串 | 180 天 |
| `SENTRY_DSN` | `.env` | 错误追踪服务 | 365 天 |
| `APISPACE_BIDDING_TOKEN` | `.env` | 招投标数据 API | 90 天 |
| IM OAuth 凭证（飞书/企微/钉钉） | DB/`.env` | 第三方 IM 平台集成 | 180 天 |

### 中级别（Medium）— 泄露影响有限

| 密钥 | 当前位置 | 用途 | 轮换建议 |
|------|----------|------|----------|
| `SUPABASE_URL` | `.env` | 数据库端点（公开可知） | 无需轮换 |
| `AI_BASE_URL` | `.env` | AI 服务端点 | 无需轮换 |
| `RATE_LIMIT_*` | `.env` | 限流配置 | N/A（非密钥） |
| `MAX_*` | `.env` | 使用限制配置 | N/A（非密钥） |

---

## 3. 推荐方案

### 方案 A：HashiCorp Vault（自托管/HCP Cloud）

**适用场景：** 需要完全控制、合规审计要求高、团队有 DevOps 能力。

#### 架构

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  FastAPI App │────>│  Vault Agent │────>│  Vault Server│
│  (容器内)    │     │  (Sidecar)   │     │  (独立部署)  │
└─────────────┘     └──────────────┘     └──────────────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │  Audit Log Storage  │
                                    └─────────────────────┘
```

#### 迁移步骤

**第 1 步：部署 Vault 服务（1-2 天）**

```bash
# 使用 Docker Compose 部署（开发/小规模）
# docker-compose.vault.yml
version: '3.8'
services:
  vault:
    image: hashicorp/vault:1.15
    cap_add:
      - IPC_LOCK
    ports:
      - "8200:8200"
    environment:
      VAULT_ADDR: http://0.0.0.0:8200
    volumes:
      - vault-data:/vault/data
      - ./vault-config:/vault/config
    command: server -config=/vault/config/config.hcl
```

**第 2 步：配置 KV Secrets Engine**

```bash
# 初始化并解封
vault operator init -key-shares=5 -key-threshold=3
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# 启用 KV v2 引擎
vault secrets enable -path=nexus kv-v2

# 写入密钥（按环境区分）
vault kv put nexus/production/database \
  supabase_url="https://xxx.supabase.co" \
  supabase_service_key="eyJhbG..." \
  supabase_jwt_secret="xxx"

vault kv put nexus/production/ai \
  openai_api_key="sk-xxx" \
  ai_fallback_api_key="sk-yyy"

vault kv put nexus/production/integrations \
  redis_url="redis://user:pass@host:6379/0" \
  sentry_dsn="https://xxx@sentry.io/yyy" \
  apispace_token="xxx"
```

**第 3 步：应用集成**

```python
# nexus_backend/app/core/secret_manager.py
import hvac
import os
import logging

logger = logging.getLogger(__name__)

class SecretManager:
    """集中化密钥管理 - Vault 后端"""

    def __init__(self):
        self._client = None
        self._cache = {}
        self._env = os.getenv("ENV", "development")

    @property
    def client(self):
        if not self._client:
            vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
            vault_token = os.getenv("VAULT_TOKEN")  # 仅这一个密钥留在 .env
            self._client = hvac.Client(url=vault_addr, token=vault_token)
        return self._client

    def get_secret(self, path: str, key: str) -> str:
        """获取密钥，带内存缓存"""
        cache_key = f"{path}/{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            full_path = f"nexus/{self._env}/{path}"
            response = self.client.secrets.kv.v2.read_secret_version(
                path=full_path, mount_point="nexus"
            )
            value = response["data"]["data"].get(key, "")
            self._cache[cache_key] = value
            return value
        except Exception as e:
            logger.error(f"Failed to read secret {path}/{key}: {e}")
            # 回退到环境变量
            fallback = os.getenv(key.upper(), "")
            if fallback:
                logger.warning(f"Using .env fallback for {key}")
            return fallback

    def clear_cache(self):
        """清除缓存（轮换后调用）"""
        self._cache.clear()

# 全局实例
secrets = SecretManager()
```

**第 4 步：修改 `database.py` 使用 SecretManager**

```python
# 改前
url = os.getenv("SUPABASE_URL", "")
key = os.getenv("SUPABASE_SERVICE_KEY", "")

# 改后
from app.core.secret_manager import secrets
url = secrets.get_secret("database", "supabase_url")
key = secrets.get_secret("database", "supabase_service_key")
```

---

### 方案 B：AWS Secrets Manager（推荐用于云部署）

**适用场景：** 已使用 AWS、需要与 AWS 生态集成、不想自运维 Vault。

#### 架构

```
┌─────────────┐     ┌──────────────────────┐
│  FastAPI App │────>│  AWS Secrets Manager │
│  (Zeabur)   │     │  (自动轮换)          │
└─────────────┘     └──────────────────────┘
      │                       │
      │  IAM Role Auth        │  CloudTrail Audit
      │                       │
```

#### 迁移步骤

**第 1 步：创建 Secrets（AWS Console 或 CLI）**

```bash
# 创建密钥组
aws secretsmanager create-secret \
  --name "nexus/production/database" \
  --secret-string '{
    "supabase_url": "https://xxx.supabase.co",
    "supabase_service_key": "eyJhbG...",
    "supabase_jwt_secret": "xxx"
  }'

aws secretsmanager create-secret \
  --name "nexus/production/ai" \
  --secret-string '{
    "openai_api_key": "sk-xxx",
    "ai_fallback_api_key": "sk-yyy"
  }'
```

**第 2 步：应用集成**

```python
# nexus_backend/app/core/secret_manager.py
import boto3
import json
import os
import logging

logger = logging.getLogger(__name__)

class AWSSecretManager:
    """集中化密钥管理 - AWS Secrets Manager 后端"""

    def __init__(self):
        self._client = None
        self._cache = {}
        self._env = os.getenv("ENV", "development")

    @property
    def client(self):
        if not self._client:
            self._client = boto3.client(
                "secretsmanager",
                region_name=os.getenv("AWS_REGION", "ap-southeast-1")
            )
        return self._client

    def get_secret(self, path: str, key: str) -> str:
        full_path = f"nexus/{self._env}/{path}"
        if full_path not in self._cache:
            try:
                response = self.client.get_secret_value(SecretId=full_path)
                self._cache[full_path] = json.loads(response["SecretString"])
            except Exception as e:
                logger.error(f"Failed to read secret {full_path}: {e}")
                return os.getenv(key.upper(), "")

        return self._cache.get(full_path, {}).get(key, "")

secrets = AWSSecretManager()
```

**第 3 步：配置自动轮换**

```bash
# 为 Supabase Service Key 配置 90 天自动轮换
aws secretsmanager rotate-secret \
  --secret-id "nexus/production/database" \
  --rotation-lambda-arn arn:aws:lambda:region:account:function:nexus-secret-rotation \
  --rotation-rules '{"AutomaticallyAfterDays": 90}'
```

---

## 4. 与 Docker/Zeabur 部署集成

### Docker 部署

```yaml
# docker-compose.yml
services:
  backend:
    image: nexus-backend:latest
    environment:
      # 仅保留 Vault/AWS 连接信息
      VAULT_ADDR: http://vault:8200
      VAULT_TOKEN_FILE: /run/secrets/vault_token
      ENV: production
    secrets:
      - vault_token

secrets:
  vault_token:
    file: ./secrets/vault_token.txt  # 此文件不入 Git
```

### Zeabur 部署

Zeabur 原生支持环境变量加密存储：

1. **短期方案**（无需额外基础设施）：
   - 所有密钥通过 Zeabur Dashboard > Service > Variables 设置
   - Zeabur 会加密存储这些变量
   - 变量自动注入为环境变量

2. **长期方案**（需要审计能力）：
   - 在 Zeabur 中只配置 `VAULT_ADDR` + `VAULT_TOKEN`
   - 应用启动时从 Vault 拉取其他所有密钥
   - 利用 Vault 的审计日志追踪密钥访问

---

## 5. 密钥轮换策略

### 轮换频率

| 密钥类别 | 轮换周期 | 自动化 | 通知 |
|----------|----------|--------|------|
| Critical（数据库密钥、AI Key） | 90 天 | 自动 | 轮换前 7 天通知 |
| High（Redis、第三方集成） | 180 天 | 半自动 | 轮换前 14 天通知 |
| Medium（监控、非敏感配置） | 365 天 | 手动 | 轮换前 30 天通知 |
| 发生泄露事件 | 立即 | 紧急手动 | 实时告警 |

### 轮换流程

```
1. 生成新密钥
2. 在密钥管理器中更新（保留旧版本）
3. 应用热加载新密钥（清除缓存）
4. 验证新密钥可用（健康检查）
5. 观察期（24小时）
6. 停用旧密钥
7. 记录审计日志
```

### 紧急轮换 Runbook

```bash
# 1. 立即生成新密钥
# 2. 更新 Vault
vault kv put nexus/production/ai openai_api_key="sk-NEW-KEY"

# 3. 通知应用重载
curl -X POST https://api.nexus.com/admin/reload-secrets \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 4. 在 OpenAI Dashboard 撤销旧密钥

# 5. 验证
curl https://api.nexus.com/health
```

---

## 6. 迁移路线图

### Phase 1（第 1-2 周）：准备

- [ ] 盘点所有密钥（本文档已完成）
- [ ] 选择密钥管理方案（Vault vs AWS SM）
- [ ] 编写 `SecretManager` 抽象层
- [ ] 编写回退逻辑（优雅降级到 `.env`）

### Phase 2（第 3-4 周）：开发环境迁移

- [ ] 部署密钥管理服务（开发环境）
- [ ] 修改 `database.py` 使用 `SecretManager`
- [ ] 修改所有读取 `os.getenv` 的密钥位置
- [ ] 本地测试通过

### Phase 3（第 5-6 周）：生产环境迁移

- [ ] 部署密钥管理服务（生产环境）
- [ ] 灰度切换：先迁移非关键密钥
- [ ] 迁移关键密钥（SUPABASE_SERVICE_KEY, OPENAI_API_KEY）
- [ ] 移除 `.env` 中的明文密钥
- [ ] 配置密钥轮换策略

### Phase 4（第 7-8 周）：加固

- [ ] 启用审计日志
- [ ] 配置轮换告警
- [ ] 编写紧急轮换 Runbook
- [ ] 团队培训

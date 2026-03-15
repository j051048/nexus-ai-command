# SAML 2.0 SSO 集成设计方案

> 企业级 SAML 2.0 Single Sign-On 集成方案，支持 Okta、Azure AD、Google Workspace

## 1. 概述

### 1.1 目标
为 Nexus AI Command 添加 SAML 2.0 SSO 能力，允许企业客户使用其现有身份提供商 (IdP) 登录，实现：
- 统一身份认证（减少密码管理负担）
- Just-In-Time (JIT) 用户预配
- SCIM 2.0 用户同步
- 多租户 SSO 配置隔离

### 1.2 核心术语
| 术语 | 说明 |
|------|------|
| SP (Service Provider) | Nexus AI Command，即我方 |
| IdP (Identity Provider) | Okta / Azure AD / Google Workspace |
| Assertion | IdP 签发的 SAML XML，包含用户身份信息 |
| ACS URL | Assertion Consumer Service URL，SP 接收断言的端点 |
| Entity ID | SP 的唯一标识符 |

## 2. SAML 认证流程

```
┌─────────┐                ┌─────────┐                ┌─────────┐
│  浏览器  │                │  Nexus  │                │   IdP   │
│ (用户)   │                │  (SP)   │                │ (Okta)  │
└────┬────┘                └────┬────┘                └────┬────┘
     │  1. 访问 /login/sso      │                          │
     │ ─────────────────────────>│                          │
     │                          │  2. 生成 AuthnRequest     │
     │  3. 302 Redirect         │                          │
     │ <─────────────────────────│                          │
     │                          │                          │
     │  4. AuthnRequest (GET/POST)                         │
     │ ────────────────────────────────────────────────────>│
     │                          │                          │
     │  5. 用户在 IdP 登录/验证  │                          │
     │ <───────────────────────────────────────────────────>│
     │                          │                          │
     │  6. POST SAMLResponse 到 ACS URL                    │
     │ ─────────────────────────>│                          │
     │                          │  7. 验证签名 + 解析断言   │
     │                          │  8. JIT 创建/更新用户     │
     │                          │  9. 创建 Session          │
     │  10. 302 → /dashboard    │                          │
     │ <─────────────────────────│                          │
```

## 3. SP 元数据配置

### 3.1 SP 元数据端点

```
GET /api/sso/metadata/{tenant_id}
```

返回标准 SAML SP 元数据 XML：

```xml
<?xml version="1.0"?>
<md:EntityDescriptor
  xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
  entityID="https://app.nexus-ai.com/saml/{tenant_id}">

  <md:SPSSODescriptor
    AuthnRequestsSigned="true"
    WantAssertionsSigned="true"
    protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">

    <md:NameIDFormat>
      urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress
    </md:NameIDFormat>

    <md:AssertionConsumerService
      Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
      Location="https://app.nexus-ai.com/api/sso/acs/{tenant_id}"
      index="0"
      isDefault="true"/>

    <md:SingleLogoutService
      Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
      Location="https://app.nexus-ai.com/api/sso/slo/{tenant_id}"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>
```

### 3.2 关键 URL

| 端点 | URL | 用途 |
|------|-----|------|
| Metadata | `/api/sso/metadata/{tenant_id}` | SP 元数据（给 IdP 导入） |
| ACS | `/api/sso/acs/{tenant_id}` | 接收 SAML Response |
| SLO | `/api/sso/slo/{tenant_id}` | 单点注销 |
| Login | `/api/sso/login/{tenant_id}` | 发起 SSO 登录 |

## 4. IdP 集成配置

### 4.1 Okta

**Okta 管理端配置**：
1. Applications → Create App Integration → SAML 2.0
2. Single sign-on URL: `https://app.nexus-ai.com/api/sso/acs/{tenant_id}`
3. Audience URI: `https://app.nexus-ai.com/saml/{tenant_id}`
4. Name ID format: EmailAddress
5. 属性映射 (Attribute Statements):

| Name | Value |
|------|-------|
| email | user.email |
| firstName | user.firstName |
| lastName | user.lastName |
| role | appuser.role |
| orgId | appuser.orgId |

### 4.2 Azure AD (Entra ID)

**Azure 管理端配置**：
1. Enterprise Applications → New application → Non-gallery
2. Single Sign-On → SAML
3. Basic SAML Configuration:
   - Identifier (Entity ID): `https://app.nexus-ai.com/saml/{tenant_id}`
   - Reply URL (ACS): `https://app.nexus-ai.com/api/sso/acs/{tenant_id}`
4. User Attributes & Claims:
   - `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress` → user.mail
   - `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname` → user.givenname
   - `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname` → user.surname
   - `role` → user.assignedroles

### 4.3 Google Workspace

**Google Admin 配置**：
1. Apps → Web and mobile apps → Add custom SAML app
2. ACS URL: `https://app.nexus-ai.com/api/sso/acs/{tenant_id}`
3. Entity ID: `https://app.nexus-ai.com/saml/{tenant_id}`
4. Name ID: Basic Information → Primary email
5. Attributes:
   - firstName → First name
   - lastName → Last name
   - email → Primary email

## 5. 属性映射

### 5.1 统一属性映射层

```python
# SAML 属性 → Nexus 用户字段的映射配置
DEFAULT_ATTRIBUTE_MAP = {
    "email": [
        "email",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        "urn:oid:0.9.2342.19200300.100.1.3",
        "mail",
    ],
    "name": [
        "displayName",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        "cn",
    ],
    "first_name": [
        "firstName",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
        "givenName",
    ],
    "last_name": [
        "lastName",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
        "sn",
    ],
    "role": [
        "role",
        "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
        "memberOf",
    ],
    "org_id": [
        "orgId",
        "organization",
        "department",
    ],
}
```

### 5.2 角色映射

IdP 中的角色/组 → Nexus 角色的映射：

```python
DEFAULT_ROLE_MAP = {
    "admin": "boss",
    "manager": "manager",
    "sales": "sales",
    "employee": "sales",  # 默认映射到 sales
    # 可在 sso_configurations 中自定义
}
```

## 6. JIT (Just-In-Time) Provisioning

当 SAML 断言中包含系统中不存在的用户时，自动创建：

```python
async def jit_provision(saml_attributes: dict, tenant_id: str) -> User:
    """
    JIT 用户预配流程：
    1. 从 SAML 断言提取用户属性
    2. 检查用户是否已存在（by email）
    3. 不存在 → 创建用户 + 分配默认角色
    4. 已存在 → 更新属性（如果 IdP 信息更新）
    """
    email = saml_attributes["email"]

    existing = await get_user_by_email(email, tenant_id)
    if existing:
        # 更新属性（姓名、角色等）
        await update_user_from_saml(existing.id, saml_attributes)
        return existing

    # 创建新用户
    new_user = await create_user(
        email=email,
        name=saml_attributes.get("name", email.split("@")[0]),
        role=map_role(saml_attributes.get("role", "employee")),
        tenant_id=tenant_id,
        auth_provider="saml",
    )

    # 审计日志
    await audit_log("user_jit_provisioned", user_id=new_user.id, tenant_id=tenant_id)
    return new_user
```

## 7. SCIM 2.0 用户同步

### 7.1 SCIM 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/scim/v2/Users` | 列出用户 |
| GET | `/api/scim/v2/Users/{id}` | 获取用户详情 |
| POST | `/api/scim/v2/Users` | 创建用户 |
| PUT | `/api/scim/v2/Users/{id}` | 全量更新用户 |
| PATCH | `/api/scim/v2/Users/{id}` | 部分更新用户 |
| DELETE | `/api/scim/v2/Users/{id}` | 停用用户 |
| GET | `/api/scim/v2/Groups` | 列出组/角色 |
| PATCH | `/api/scim/v2/Groups/{id}` | 更新组成员 |

### 7.2 SCIM User Schema

```json
{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
  "id": "user_uuid",
  "userName": "john@company.com",
  "name": {
    "givenName": "John",
    "familyName": "Doe"
  },
  "emails": [
    { "value": "john@company.com", "primary": true }
  ],
  "active": true,
  "externalId": "okta_user_id",
  "groups": [
    { "value": "manager_group_id", "display": "Managers" }
  ]
}
```

### 7.3 同步策略

- **IdP → Nexus** (入方向)：IdP 推送变更到 SCIM 端点
- **冲突处理**：IdP 为主，Nexus 字段被覆盖（email 除外）
- **删除策略**：SCIM DELETE → 用户标记为 `inactive`（不物理删除）
- **认证**：SCIM 请求使用 Bearer Token（每个租户独立 token）

## 8. 数据库表设计

### 8.1 sso_configurations

```sql
CREATE TABLE sso_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    -- IdP 配置
    idp_type VARCHAR(50) NOT NULL,  -- 'okta', 'azure_ad', 'google', 'custom'
    idp_entity_id TEXT NOT NULL,
    idp_sso_url TEXT NOT NULL,
    idp_slo_url TEXT,
    idp_certificate TEXT NOT NULL,  -- X.509 证书 (PEM)

    -- SP 配置
    sp_entity_id TEXT NOT NULL,
    sp_acs_url TEXT NOT NULL,

    -- 属性映射 (JSON)
    attribute_map JSONB DEFAULT '{}',
    role_map JSONB DEFAULT '{}',

    -- SCIM 配置
    scim_enabled BOOLEAN DEFAULT FALSE,
    scim_token_hash TEXT,

    -- JIT 配置
    jit_enabled BOOLEAN DEFAULT TRUE,
    default_role VARCHAR(50) DEFAULT 'sales',

    -- 状态
    is_active BOOLEAN DEFAULT FALSE,
    enforce_sso BOOLEAN DEFAULT FALSE,  -- 强制 SSO（禁用密码登录）

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(tenant_id)  -- 每个租户一个 SSO 配置
);
```

### 8.2 sso_sessions

```sql
CREATE TABLE sso_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    sso_config_id UUID NOT NULL REFERENCES sso_configurations(id),

    -- SAML Session
    session_index TEXT,          -- IdP 的 SessionIndex
    name_id TEXT NOT NULL,       -- SAML NameID
    name_id_format TEXT,

    -- Session 元数据
    idp_session_id TEXT,
    login_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_active_at TIMESTAMPTZ DEFAULT NOW(),

    -- 审计
    ip_address INET,
    user_agent TEXT,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sso_sessions_user ON sso_sessions(user_id, is_active);
CREATE INDEX idx_sso_sessions_name_id ON sso_sessions(name_id, tenant_id);
CREATE INDEX idx_sso_sessions_expires ON sso_sessions(expires_at) WHERE is_active = TRUE;
```

### 8.3 scim_sync_log

```sql
CREATE TABLE scim_sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    operation VARCHAR(20) NOT NULL,  -- 'create', 'update', 'delete', 'activate', 'deactivate'
    resource_type VARCHAR(20) NOT NULL,  -- 'User', 'Group'
    external_id TEXT,
    nexus_user_id UUID,
    request_body JSONB,
    status VARCHAR(20) DEFAULT 'success',  -- 'success', 'failed', 'conflict'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 9. 安全考虑

| 威胁 | 缓解措施 |
|------|---------|
| SAML Response 重放 | 检查 `InResponseTo` + 5 分钟有效期 + 一次性 ID 检查 |
| XML 签名绕过 | 使用 xmlsec1 / python3-saml 严格校验 |
| XXE 攻击 | 禁用 XML 外部实体解析 |
| 中间人攻击 | 强制 HTTPS + 签名验证 |
| 会话固定 | SSO 登录后重新生成 session ID |
| SCIM Token 泄露 | Token 哈希存储 + 速率限制 |

## 10. 实施路径

### Phase 1：基础 SAML SSO（2 周）
- SP 元数据端点
- AuthnRequest 生成
- SAML Response 解析 & 验证
- JIT 用户预配
- Okta 集成测试

### Phase 2：多 IdP 支持（1 周）
- Azure AD 适配
- Google Workspace 适配
- 属性映射配置 UI

### Phase 3：SCIM 同步（2 周）
- SCIM 2.0 核心端点
- 用户 CRUD 同步
- 组/角色同步
- 冲突处理

### Phase 4：企业级特性（1 周）
- 强制 SSO 模式
- Single Logout (SLO)
- SSO Session 管理 UI
- 审计日志增强

### 推荐库
- Python: `python3-saml` (OneLogin) 或 `pysaml2`
- 前端: 无需额外库（标准 HTTP 重定向流程）

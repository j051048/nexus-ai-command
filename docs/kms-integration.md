# KMS 集成方案

> 将加密密钥从环境变量迁移到 KMS (Key Management Service) 的实施方案

## 1. 背景与目标

当前 `nexus_backend/app/services/encryption_service.py` 使用 `EnvKeyProvider` 从 `ENCRYPTION_KEY` 环境变量读取 Fernet 密钥。虽然已有 `KeyProvider` 抽象和 `VaultKeyProvider` 存根，但生产环境仍依赖环境变量，存在以下风险：

- 密钥明文存储在环境变量/配置文件中
- 无密钥自动轮换能力
- 无硬件安全模块 (HSM) 保护
- 无密钥使用审计日志

**目标**：实现密钥层次结构，将 Master Key 托管到 KMS，Data Encryption Key (DEK) 由 KMS 生成并加密存储。

## 2. 密钥层次结构

```
┌─────────────────────────────────────┐
│         KMS Master Key (KEK)        │  ← 永不离开 KMS/HSM
│    AWS CMK / GCP CryptoKey / Vault  │
└──────────────┬──────────────────────┘
               │ Encrypt/Decrypt
               ▼
┌─────────────────────────────────────┐
│   Encrypted Data Encryption Key     │  ← 加密后存储在数据库/配置
│         (Wrapped DEK)               │
└──────────────┬──────────────────────┘
               │ 解密后在内存中使用
               ▼
┌─────────────────────────────────────┐
│      Plaintext DEK (Fernet Key)     │  ← 仅存在于应用内存
│    用于 encrypt()/decrypt() 操作    │
└─────────────────────────────────────┘
```

**信封加密 (Envelope Encryption)** 流程：
1. 应用启动时，从存储中读取 Wrapped DEK
2. 调用 KMS API 解密 Wrapped DEK → 得到明文 DEK
3. 用明文 DEK 进行 Fernet 加密/解密
4. 明文 DEK 仅保留在内存中，进程退出即销毁

## 3. 方案对比

| 维度 | AWS KMS | GCP Cloud KMS | HashiCorp Vault Transit |
|------|---------|---------------|------------------------|
| HSM 保护 | FIPS 140-2 Level 2/3 | FIPS 140-2 Level 3 | 软件 (可接 HSM) |
| 自动轮换 | 年度自动轮换 | 可配置周期 | 手动/API 触发 |
| 多云支持 | AWS 锁定 | GCP 锁定 | 跨云 |
| 价格 | $1/key/月 + $0.03/万次 | $0.06/key/版本/月 + $0.03/万次 | 开源免费 (自运维) / HCP Vault |
| 延迟 | ~10ms | ~10ms | ~5ms (同网络) |
| 集成复杂度 | 低 (boto3) | 低 (google-cloud-kms) | 中 (HTTP API) |

### 推荐策略
- **AWS 部署**：AWS KMS
- **GCP 部署**：GCP Cloud KMS
- **混合/本地部署**：HashiCorp Vault Transit
- **当前推荐**：HashiCorp Vault Transit（已有 `VaultKeyProvider` 存根，且跨云）

## 4. 实现方案

### 4.1 AWS KMS 集成

```python
# nexus_backend/app/services/encryption_service.py — AWSKMSKeyProvider

import boto3
import base64

class AWSKMSKeyProvider(KeyProvider):
    """AWS KMS Envelope Encryption provider."""

    def __init__(self, key_id: str = None, region: str = None):
        self._key_id = key_id or os.getenv("AWS_KMS_KEY_ID")
        self._region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("kms", region_name=self._region)
        self._cached_dek: str | None = None

    def get_encryption_key(self) -> str:
        if self._cached_dek:
            return self._cached_dek

        # 读取存储的 Wrapped DEK
        wrapped_dek = self._load_wrapped_dek()

        if wrapped_dek:
            # 解密已有的 DEK
            resp = self._client.decrypt(
                CiphertextBlob=base64.b64decode(wrapped_dek),
                KeyId=self._key_id,
            )
            self._cached_dek = base64.urlsafe_b64encode(resp["Plaintext"]).decode()
        else:
            # 首次：生成新 DEK
            resp = self._client.generate_data_key(
                KeyId=self._key_id,
                KeySpec="AES_256",
            )
            self._cached_dek = base64.urlsafe_b64encode(resp["Plaintext"]).decode()
            # 保存 Wrapped DEK
            self._save_wrapped_dek(
                base64.b64encode(resp["CiphertextBlob"]).decode()
            )

        return self._cached_dek

    def rotate_key(self) -> str:
        # 生成新 DEK，重新加密所有数据
        resp = self._client.generate_data_key(
            KeyId=self._key_id,
            KeySpec="AES_256",
        )
        new_dek = base64.urlsafe_b64encode(resp["Plaintext"]).decode()
        self._save_wrapped_dek(
            base64.b64encode(resp["CiphertextBlob"]).decode()
        )
        self._cached_dek = new_dek
        return new_dek

    def _load_wrapped_dek(self) -> str | None:
        """从数据库或文件加载 Wrapped DEK."""
        # 实现：从 system_configs 表读取
        ...

    def _save_wrapped_dek(self, wrapped: str) -> None:
        """持久化 Wrapped DEK."""
        # 实现：写入 system_configs 表
        ...
```

### 4.2 GCP Cloud KMS 集成

```python
from google.cloud import kms

class GCPKMSKeyProvider(KeyProvider):
    """GCP Cloud KMS Envelope Encryption provider."""

    def __init__(self):
        self._project = os.getenv("GCP_PROJECT_ID")
        self._location = os.getenv("GCP_KMS_LOCATION", "global")
        self._keyring = os.getenv("GCP_KMS_KEYRING", "nexus")
        self._key = os.getenv("GCP_KMS_KEY", "data-encryption-key")
        self._client = kms.KeyManagementServiceClient()
        self._cached_dek: str | None = None

    @property
    def _key_name(self) -> str:
        return self._client.crypto_key_path(
            self._project, self._location, self._keyring, self._key
        )

    def get_encryption_key(self) -> str:
        if self._cached_dek:
            return self._cached_dek

        wrapped_dek = self._load_wrapped_dek()
        if wrapped_dek:
            resp = self._client.decrypt(
                request={"name": self._key_name, "ciphertext": base64.b64decode(wrapped_dek)}
            )
            self._cached_dek = base64.urlsafe_b64encode(resp.plaintext).decode()
        else:
            # Generate new DEK locally, encrypt with KMS
            from cryptography.fernet import Fernet
            plaintext_dek = Fernet.generate_key()
            resp = self._client.encrypt(
                request={"name": self._key_name, "plaintext": plaintext_dek}
            )
            self._save_wrapped_dek(base64.b64encode(resp.ciphertext).decode())
            self._cached_dek = plaintext_dek.decode()

        return self._cached_dek

    def rotate_key(self) -> str:
        from cryptography.fernet import Fernet
        new_dek = Fernet.generate_key()
        resp = self._client.encrypt(
            request={"name": self._key_name, "plaintext": new_dek}
        )
        self._save_wrapped_dek(base64.b64encode(resp.ciphertext).decode())
        self._cached_dek = new_dek.decode()
        return self._cached_dek
```

### 4.3 HashiCorp Vault Transit 集成

```python
class VaultTransitKeyProvider(KeyProvider):
    """Vault Transit secret engine — KMS-as-a-service."""

    def __init__(self):
        self._vault_addr = os.getenv("VAULT_ADDR")
        self._token = os.getenv("VAULT_TOKEN")
        self._key_name = os.getenv("VAULT_TRANSIT_KEY", "nexus-dek")
        self._cached_dek: str | None = None

    def get_encryption_key(self) -> str:
        if self._cached_dek:
            return self._cached_dek

        import httpx
        wrapped_dek = self._load_wrapped_dek()

        if wrapped_dek:
            # Decrypt via Vault Transit
            resp = httpx.post(
                f"{self._vault_addr}/v1/transit/decrypt/{self._key_name}",
                headers={"X-Vault-Token": self._token},
                json={"ciphertext": wrapped_dek},
                timeout=5.0,
            )
            resp.raise_for_status()
            plaintext_b64 = resp.json()["data"]["plaintext"]
            self._cached_dek = base64.b64decode(plaintext_b64).decode()
        else:
            # Generate DEK locally, encrypt with Vault Transit
            from cryptography.fernet import Fernet
            dek = Fernet.generate_key().decode()

            resp = httpx.post(
                f"{self._vault_addr}/v1/transit/encrypt/{self._key_name}",
                headers={"X-Vault-Token": self._token},
                json={"plaintext": base64.b64encode(dek.encode()).decode()},
                timeout=5.0,
            )
            resp.raise_for_status()
            wrapped = resp.json()["data"]["ciphertext"]
            self._save_wrapped_dek(wrapped)
            self._cached_dek = dek

        return self._cached_dek

    def rotate_key(self) -> str:
        import httpx
        # Rotate Vault Transit key (adds new key version)
        httpx.post(
            f"{self._vault_addr}/v1/transit/keys/{self._key_name}/rotate",
            headers={"X-Vault-Token": self._token},
            timeout=5.0,
        ).raise_for_status()

        # Re-encrypt wrapped DEK with new key version
        old_wrapped = self._load_wrapped_dek()
        resp = httpx.post(
            f"{self._vault_addr}/v1/transit/rewrap/{self._key_name}",
            headers={"X-Vault-Token": self._token},
            json={"ciphertext": old_wrapped},
            timeout=5.0,
        )
        resp.raise_for_status()
        new_wrapped = resp.json()["data"]["ciphertext"]
        self._save_wrapped_dek(new_wrapped)

        return self._cached_dek  # DEK itself unchanged, only wrapping updated
```

### 4.4 与现有代码的集成

当前 `encryption_service.py` 已有 `KeyProvider` 抽象，集成只需修改 `_resolve_key_provider()`：

```python
def _resolve_key_provider() -> KeyProvider:
    """Resolve key provider based on KEY_PROVIDER env var."""
    provider_type = os.getenv("KEY_PROVIDER", "env").lower()

    if provider_type == "aws_kms":
        return AWSKMSKeyProvider()
    elif provider_type == "gcp_kms":
        return GCPKMSKeyProvider()
    elif provider_type == "vault_transit":
        return VaultTransitKeyProvider()
    elif provider_type == "vault":
        return VaultKeyProvider()  # 现有的简单 Vault KV provider

    return EnvKeyProvider()
```

**环境变量配置**：

```bash
# AWS KMS
KEY_PROVIDER=aws_kms
AWS_KMS_KEY_ID=arn:aws:kms:us-east-1:123456:key/abcd-1234
AWS_REGION=us-east-1

# GCP Cloud KMS
KEY_PROVIDER=gcp_kms
GCP_PROJECT_ID=my-project
GCP_KMS_LOCATION=global
GCP_KMS_KEYRING=nexus
GCP_KMS_KEY=data-encryption-key

# Vault Transit
KEY_PROVIDER=vault_transit
VAULT_ADDR=https://vault.internal:8200
VAULT_TOKEN=hvs.xxx
VAULT_TRANSIT_KEY=nexus-dek
```

## 5. 密钥轮换策略

### 5.1 轮换流程

```
1. 调用 KMS 轮换 Master Key（或创建新版本）
2. 用新 Master Key 重新包装 (rewrap) DEK
3. 如需轮换 DEK 本身：
   a. 生成新 DEK
   b. 用新 Master Key 加密新 DEK
   c. 启动后台任务：用旧 DEK 解密 → 用新 DEK 重新加密所有数据
   d. 验证完成后删除旧 Wrapped DEK
```

### 5.2 轮换频率建议

| 密钥类型 | 轮换频率 | 触发方式 |
|---------|---------|---------|
| Master Key (KEK) | 每年 1 次 | KMS 自动 / 手动 |
| Data Encryption Key (DEK) | 每季度 1 次 | 定时任务 |
| 紧急轮换 | 即时 | 安全事件触发 |

### 5.3 数据重新加密脚本

```python
async def rotate_dek_and_reencrypt():
    """DEK 轮换 + 数据重新加密（后台任务）"""
    old_fernet = EncryptionService._get_fernet()

    # 1. 轮换 DEK
    new_key = _key_provider.rotate_key()
    new_fernet = Fernet(new_key.encode())

    # 2. 重新加密所有敏感数据
    tables_with_encrypted_fields = {
        "llm_model_configs": ["api_key"],
        # 添加其他包含加密字段的表
    }

    for table, fields in tables_with_encrypted_fields.items():
        rows = supabase.table(table).select("id," + ",".join(fields)).execute()
        for row in rows.data:
            updates = {}
            for field in fields:
                if row.get(field) and EncryptionService.is_encrypted(row[field]):
                    plaintext = old_fernet.decrypt(row[field].encode()).decode()
                    updates[field] = new_fernet.encrypt(plaintext.encode()).decode()
            if updates:
                supabase.table(table).update(updates).eq("id", row["id"]).execute()
```

## 6. 成本估算

### 月度成本（基于 1000 次/天加密操作）

| 服务 | 密钥费用 | API 调用费 | 月总成本 |
|------|---------|-----------|---------|
| AWS KMS | $1/key | ~$0.90 (30k 次) | **~$2** |
| GCP Cloud KMS | $0.06/key | ~$0.90 (30k 次) | **~$1** |
| Vault (self-hosted) | 免费 | 免费 | **$0** (运维成本另计) |
| HCP Vault | $0.03/secret/月 | 含在内 | **~$1.50** |

> 注：信封加密模式下，KMS API 调用仅在应用启动和 DEK 轮换时发生，日常加解密使用内存中的 DEK，因此 API 调用量极低，实际成本接近最低档。

## 7. 迁移路径

### Phase 1：准备（1 天）
1. 在目标 KMS 中创建 Master Key
2. 添加新 KeyProvider 实现到 `encryption_service.py`
3. 本地测试通过

### Phase 2：灰度迁移（1 周）
1. Staging 环境设置 `KEY_PROVIDER=vault_transit`
2. 运行数据重新加密脚本
3. 验证所有加密/解密操作正常

### Phase 3：生产上线（1 天）
1. 生产环境切换 `KEY_PROVIDER`
2. 运行重新加密脚本
3. 移除 `ENCRYPTION_KEY` 环境变量
4. 配置密钥轮换定时任务

### Phase 4：验证 & 清理（1 周）
1. 监控加密操作日志
2. 确认无 fallback 到环境变量
3. 更新运维文档

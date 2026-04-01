# 环境变量配置更新

## 新增配置项

### Langfuse (LLM 追踪)

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

### HashiCorp Vault (密钥管理)

```bash
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=hvs.xxx
```

### Cohere (Rerank)

```bash
COHERE_API_KEY=xxx
```

## 迁移步骤

1. **安装依赖**:

   ```bash
   pip install langfuse hvac cohere
   ```

1. **配置 Vault**:

   ```bash
   # 启动 Vault (开发模式)
   vault server -dev

   # 存储密钥
   vault kv put nexus/openai api_key="sk-xxx"
   vault kv put nexus/encryption key="xxx"
   ```

1. **更新代码引用**:

   ```python
   # 旧方式
   api_key = os.getenv("OPENAI_API_KEY")

   # 新方式
   from app.core.vault_secrets import get_openai_api_key
   api_key = get_openai_api_key()
   ```

1. **验证配置**:

   ```bash
   python -c "from app.core.vault_secrets import get_openai_api_key; print('OK' if get_openai_api_key() else 'FAIL')"
   ```

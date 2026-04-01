# Langfuse Zeabur 集成指南

## 第一步: 在 Zeabur 部署 Langfuse 服务

### 1. 创建 Langfuse 服务

在 Zeabur 项目中添加新服务:
- 选择 "Docker Image"
- 镜像: `langfuse/langfuse:latest`
- 端口: 3000

### 2. 配置环境变量

在 Langfuse 服务中添加以下环境变量:

```bash
# 数据库连接 (使用你已部署的 PostgreSQL)
DATABASE_URL=postgresql://root:NEl53XOw2en0I79Svrhzj6qiaD814Tub@119.28.149.108:32171/zeabur

# NextAuth 配置 (生成随机密钥)
NEXTAUTH_SECRET=<生成一个32位随机字符串>
SALT=<生成一个32位随机字符串>

# Langfuse 访问地址 (部署后 Zeabur 会提供)
NEXTAUTH_URL=https://<your-langfuse-service>.zeabur.app

# 可选: 禁用遥测
TELEMETRY_ENABLED=false
```

### 3. 生成随机密钥

在本地终端运行:
```bash
# 生成 NEXTAUTH_SECRET
openssl rand -base64 32

# 生成 SALT
openssl rand -base64 32
```

## 第二步: 初始化数据库

Langfuse 首次启动会自动创建所需的表结构。等待服务启动完成后:

1. 访问 `https://<your-langfuse-service>.zeabur.app`
2. 创建管理员账号
3. 登录后进入 Settings → API Keys
4. 创建新的 API Key,记录:
   - Public Key (pk-lf-xxx)
   - Secret Key (sk-lf-xxx)

## 第三步: 配置 Nexus 后端

更新 Nexus 后端的环境变量:

```bash
# Langfuse 配置
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://<your-langfuse-service>.zeabur.app
```

## 第四步: 验证集成

运行测试脚本:

```python
from app.core.langfuse_integration import get_langfuse_handler

handler = get_langfuse_handler()
if handler:
    print("✅ Langfuse 连接成功")
else:
    print("❌ Langfuse 连接失败")
```

## 故障排查

### 问题1: 数据库连接失败
- 检查 DATABASE_URL 是否正确
- 确认 PostgreSQL 服务正在运行
- 检查网络连接和防火墙规则

### 问题2: NEXTAUTH_URL 不匹配
- 确保 NEXTAUTH_URL 与实际访问地址一致
- 部署后需要更新此变量

### 问题3: Langfuse 服务无法启动
- 查看 Zeabur 日志
- 确认所有必需环境变量已设置
- 检查镜像版本是否兼容

## 安全建议

1. **生产环境**: 使用强随机密钥
2. **数据库**: 定期备份 PostgreSQL 数据
3. **访问控制**: 配置 Zeabur 的访问限制
4. **密钥轮换**: 定期更新 API Keys

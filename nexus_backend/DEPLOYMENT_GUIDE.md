"# 数据库迁移部署指南

## 📋 需要执行的迁移文件

### 方式一：通过 Supabase Dashboard 执行（推荐）

1. 打开 Supabase Dashboard: https://supabase.com/dashboard
2. 选择您的项目
3. 进入 **SQL Editor** 页面
4. 按顺序执行以下迁移文件：

### 🔴 必须执行的迁移文件

| 序号 | 文件路径 | 说明 |
|------|---------|------|
| 1 | `nexus_backend/supabase_migrations/migrations/20241215_p0_security_fixes.sql` | **P0安全修复** - 新增表、索引、函数 |

### 🟡 可选执行的迁移文件（如果之前未执行）

| 序号 | 文件路径 | 说明 |
|------|---------|------|
| 1 | `nexus_backend/supabase_migrations/migrations/20240201000000_add_ai_settings.sql` | AI设置表 |
| 2 | `nexus_backend/supabase_migrations/migrations/20240210000000_add_token_usage_tables.sql` | Token使用统计表 |
| 3 | `nexus_backend/supabase_migrations/migrations/20240204000000_extended_rls_policies.sql` | RLS策略增强 |
| 4 | `nexus_backend/supabase_migrations/migrations/20250213_match_documents_org_param.sql` | 向量搜索org_id参数 |

---

## 📝 执行步骤

### 步骤1：打开 SQL Editor

1. 登录 Supabase Dashboard
2. 选择项目
3. 点击左侧菜单 **SQL Editor**
4. 点击 **New query**

### 步骤2：复制并执行迁移脚本

打开以下文件，复制全部内容，粘贴到 SQL Editor 中执行：

```
文件: nexus_backend/supabase_migrations/migrations/20241215_p0_security_fixes.sql
```

### 步骤3：验证迁移成功

执行以下 SQL 验证新表是否创建成功：

```sql
-- 检查新表是否存在
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'tenant_credits',
    'agent_traces', 
    'semantic_cache',
    'rate_limit_events',
    'security_events',
    'prompt_versions'
);

-- 检查函数是否存在
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public'
AND routine_name IN (
    'get_user_org_id',
    'consume_tenant_credit',
    'check_ip_block'
);

-- 检查索引是否创建
SELECT indexname 
FROM pg_indexes 
WHERE schemaname = 'public'
AND indexname LIKE 'idx_%';
```

---

## ⚠️ 注意事项

1. **备份数据**：执行迁移前建议备份数据库
2. **测试环境先执行**：建议先在测试环境验证
3. **检查错误**：执行后检查是否有错误信息
4. **RLS策略**：确保RLS策略正确应用

---

## 🔧 如果遇到问题

### 问题1：表已存在错误

```
ERROR: relation \"xxx\" already exists
```

**解决方案**：使用 `CREATE TABLE IF NOT EXISTS` 已处理，可忽略此错误。

### 问题2：索引已存在错误

```
ERROR: relation \"idx_xxx\" already exists
```

**解决方案**：使用 `CREATE INDEX IF NOT EXISTS` 已处理，可忽略此错误。

### 问题3：权限不足

```
ERROR: permission denied
```

**解决方案**：确保使用具有足够权限的用户执行（通常是 postgres 或 service_role）。

---

## 📊 迁移完成后验证清单

- [ ] `tenant_credits` 表创建成功
- [ ] `agent_traces` 表创建成功
- [ ] `semantic_cache` 表创建成功
- [ ] `rate_limit_events` 表创建成功
- [ ] `security_events` 表创建成功
- [ ] `prompt_versions` 表创建成功
- [ ] `get_user_org_id` 函数创建成功
- [ ] `consume_tenant_credit` 函数创建成功
- [ ] `check_ip_block` 函数创建成功
- [ ] 所有索引创建成功
- [ ] RLS策略已启用

---

## 🚀 下一步

迁移完成后，重启后端服务：

```bash
cd nexus_backend
uvicorn app.main:app --reload
```"

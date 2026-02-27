# Supabase Migration 管理指南

## 概述

本项目使用 Supabase SQL 迁移文件管理数据库 Schema。所有迁移文件存放在 `nexus_backend/supabase_migrations/migrations/` 目录中。

## 迁移文件命名规范

```
YYYYMMDD_NNN_description.sql
```

- `YYYYMMDD` — 日期（如 20260227）
- `NNN` — 当天序号（如 001, 002），避免同一天多个迁移冲突
- `description` — 简短英文描述，使用下划线分隔（如 `add_user_preferences`）

### 示例

```
20260227_001_add_user_preferences.sql
20260227_002_fix_approval_chain_columns.sql
20260228_001_create_audit_events_table.sql
```

## 创建新迁移

### 方法 1: 手动创建

1. 在 `migrations/` 目录下创建新的 `.sql` 文件：
   ```bash
   touch nexus_backend/supabase_migrations/migrations/20260228_001_your_description.sql
   ```

2. 编写 SQL，使用 `IF NOT EXISTS` / `IF EXISTS` 保证幂等性：
   ```sql
   -- 创建表（幂等）
   CREATE TABLE IF NOT EXISTS public.your_table (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       name TEXT NOT NULL,
       created_at TIMESTAMPTZ DEFAULT now()
   );

   -- 添加列（幂等）
   DO $$
   BEGIN
       IF NOT EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_name = 'your_table' AND column_name = 'new_column'
       ) THEN
           ALTER TABLE public.your_table ADD COLUMN new_column TEXT;
       END IF;
   END $$;

   -- 启用 RLS
   ALTER TABLE public.your_table ENABLE ROW LEVEL SECURITY;

   -- 创建 RLS 策略（先删后建）
   DROP POLICY IF EXISTS "org_isolation" ON public.your_table;
   CREATE POLICY "org_isolation" ON public.your_table
       FOR ALL USING (organization_id = (SELECT organization_id FROM public.users WHERE id = auth.uid()));
   ```

### 方法 2: 使用 Supabase CLI

```bash
# 生成差异迁移（对比本地和远程 Schema）
supabase db diff --linked --schema public -f your_description

# 这会在 supabase/migrations/ 下生成带时间戳的文件
# 手动移动到我们的目录并重命名
```

## 应用迁移

### 本地开发

```bash
# 推送到本地 Supabase 实例
supabase db push --local

# 或直接在 Supabase Dashboard SQL Editor 中执行
```

### 生产环境

```bash
# 推送到远程 Supabase 项目
supabase db push --linked

# 或通过 Supabase Dashboard -> SQL Editor 手动执行
```

### 自动迁移（可选）

设置环境变量 `AUTO_MIGRATE=true` 后，应用启动时会自动检查并记录待执行的迁移。
详见 `nexus_backend/app/core/migration_runner.py`。

## 回滚策略

Supabase 不原生支持回滚。推荐做法：

1. **创建反向迁移**: 新建一个迁移文件来撤销变更
   ```sql
   -- 20260228_002_rollback_your_description.sql
   ALTER TABLE public.your_table DROP COLUMN IF EXISTS new_column;
   ```

2. **使用 Point-in-Time Recovery**: 在 Supabase Dashboard 中恢复到指定时间点

## 最佳实践

1. **幂等性**: 所有迁移必须可重复执行（使用 IF NOT EXISTS / IF EXISTS）
2. **小步前进**: 每个迁移文件只做一件事
3. **先测试**: 在本地或 staging 环境先测试迁移
4. **备份**: 生产环境执行前确保有最新备份
5. **RLS**: 新表必须启用 RLS 并添加 organization_id 隔离策略
6. **索引**: 为常用查询字段添加索引，特别是 organization_id 和外键

## 常见操作模板

### 添加列

```sql
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'target_table'
          AND column_name = 'new_column'
    ) THEN
        ALTER TABLE public.target_table ADD COLUMN new_column TEXT DEFAULT '';
    END IF;
END $$;
```

### 创建索引

```sql
CREATE INDEX IF NOT EXISTS idx_table_column
    ON public.target_table (column_name);
```

### 创建 RPC 函数

```sql
CREATE OR REPLACE FUNCTION public.my_function(p_param TEXT)
RETURNS TABLE (id UUID, name TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT t.id, t.name FROM public.target_table t
    WHERE t.column = p_param;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

## 目录结构

```
nexus_backend/supabase_migrations/
├── migrations/               # 按时间排序的迁移文件
│   ├── 20240126000000_initial_schema.sql
│   ├── 20240126999999_seed_data.sql
│   ├── ...
│   └── 20260227_xxx_latest.sql
├── MIGRATION_GUIDE.md        # 本指南
└── *.sql                     # 顶层 SQL 文件（功能模块 Schema）
```

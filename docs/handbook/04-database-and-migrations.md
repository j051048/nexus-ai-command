# 数据库与迁移

## 规则

- 正向迁移位于 `supabase/migrations` 根目录，按文件名排序执行。
- 已进入共享环境的迁移不可编辑；修复必须追加兼容迁移。
- `organization_id` 是新代码的标准租户列；兼容历史 `org_id` 时必须有明确收敛迁移。
- 新租户表必须同时提交 RLS enable、策略、索引和隔离测试。
- 多表原子业务使用 PostgreSQL RPC/事务函数，不在客户端串联多个写请求。

## 必跑检查

```bash
python scripts/check_migration_governance.py
python scripts/scan_migration_schema_conflicts.py
python scripts/scan_rls_coverage.py
python scripts/scan_rls_policy_columns.py
python scripts/audit_schema_convergence.py
```

生产前在空白临时数据库重放全部迁移，再用两个组织验证互不可见。`machine_generated_master_setup.sql` 不是日常增量迁移来源。

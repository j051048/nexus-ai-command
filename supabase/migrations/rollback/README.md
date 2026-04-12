# Database Migration Rollback Scripts

本目录包含最近 10 个关键迁移的回滚(down)脚本。

## 使用方式

```bash
# 在 Supabase SQL Editor 或 psql 中执行对应的 .down.sql 文件
psql $DATABASE_URL -f rollback/20260411_004_lead_scoring.down.sql
```

## 风险等级说明

| 风险等级 | 含义 | 操作要求 |
|---------|------|---------|
| **CRITICAL** | 涉及计费/支付核心表 | 必须备份数据 + 业务方审批后方可执行 |
| **HIGH** | 涉及整表删除或跨迁移依赖 | 必须确认无生产数据或已备份 |
| **MEDIUM** | 仅删除列/索引，影响范围可控 | 确认相关功能可降级后执行 |

## 回滚脚本清单

| 迁移文件 | 风险 | 回滚内容 |
|---------|------|---------|
| `20260408_memory_rbac_and_semantic_tags` | HIGH | 删除 `knowledge_graph_triples` 表 + 移除 `conversation_memories` 列 |
| `20260409_kg_temporal_validity` | MEDIUM | 移除 `valid_from`/`valid_to` 列 |
| `20260410_add_org_brand_columns` | MEDIUM | 移除 `brand` JSONB 列 |
| `20260410_fix_kg_schema_and_rbac` | HIGH | 替换 RLS 策略，保留已有列 |
| `20260410_report_engine` | HIGH | 删除 `saved_reports` + `report_schedules` 表 |
| `20260411_001_subscriptions` | **CRITICAL** | 删除 `subscriptions` + `tenant_subscriptions` 表 |
| `20260411_002_tenant_credits_quotas` | **CRITICAL** | 删除 `tenant_credits` + `tenant_quotas` + `consume_tenant_credit` RPC |
| `20260411_003_tenant_stripe_fields` | **CRITICAL** | 移除 Stripe 集成列 |
| `20260411_004_lead_scoring` | MEDIUM | 移除 AI 评分列 |
| `20260411_005_hr_write_rls` | MEDIUM | 仅移除 RLS 策略，保留表和数据 |

## 回滚顺序

如需回滚多个连续迁移，**必须按逆序执行**：

```
20260411_005 → 20260411_004 → 20260411_003 → 20260411_002 → 20260411_001
→ 20260410_report_engine → 20260410_fix_kg → 20260410_brand
→ 20260409 → 20260408
```

## 注意事项

1. 所有回滚脚本使用 `IF EXISTS` 保证幂等性（可安全重复执行）
2. 回滚脚本包裹在 `BEGIN/COMMIT` 事务中，失败时自动回滚
3. `20260410_fix_kg_schema_and_rbac` 与 `20260408` 有列定义重叠，其回滚脚本只处理策略和索引
4. **生产环境执行前务必先在 staging 验证**

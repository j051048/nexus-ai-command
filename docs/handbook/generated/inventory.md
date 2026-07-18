# 工程事实清单

> 本文件由 `python scripts/generate_handover_inventory.py` 生成。不要手工修改。

## 规模

| 范围 | 文件数 | 代码行数 |
|---|---:|---:|
| 前端 `src` | 509 | 98561 |
| 后端 `nexus_backend/app` | 559 | 157440 |
| 前端单元/集成测试 | 49 | 6469 |
| 后端测试 | 186 | 30770 |
| Playwright E2E | 15 | 2876 |

## 运行时资产

| 资产 | 数量/值 | 权威来源 |
|---|---:|---|
| 前端页面文件 | 74 | `src/pages` |
| FastAPI 路由模块 | 105 | `nexus_backend/app/routers` |
| 后端服务模块 | 184 | `nexus_backend/app/services` |
| Agent 工具模块 | 67 | `nexus_backend/app/tools` |
| 正向 SQL 迁移 | 121 | `supabase/migrations/*.sql` |
| 回滚 SQL | 10 | `supabase/migrations/rollback` |
| 强制生产聊天模型 | `deepseek-v4-flash` | `nexus_backend/app/core/config.py` |

## 前端最大文件

这些文件是渐进拆分清单，不代表可以无测试地批量重写。

| 文件 | 行数 |
|---|---:|
| `src/integrations/supabase/types.ts` | 1298 |
| `src/lib/i18n.ts` | 1274 |
| `src/pages/OACenter.tsx` | 1255 |
| `src/lib/animations.ts` | 1185 |
| `src/pages/crm/CustomerDetailSheet.tsx` | 1086 |
| `src/hooks/useVMD.ts` | 1052 |
| `src/pages/LLMModelManagement.tsx` | 1051 |
| `src/pages/OrgChartPage.tsx` | 991 |
| `src/pages/BattlecardLibrary.tsx` | 933 |
| `src/hooks/useAIStream.ts` | 830 |

# 工程事实清单

> 本文件由 `python scripts/generate_handover_inventory.py` 生成。不要手工修改。

## 规模

| 范围 | 文件数 | 代码行数 |
|---|---:|---:|
| 前端 `src` | 586 | 103883 |
| 后端 `nexus_backend/app` | 631 | 176211 |
| 前端单元/集成测试 | 68 | 7819 |
| 后端测试 | 245 | 38766 |
| Playwright E2E | 19 | 3406 |

## 运行时资产

| 资产 | 数量/值 | 权威来源 |
|---|---:|---|
| 前端页面文件 | 76 | `src/pages` |
| FastAPI 路由模块 | 112 | `nexus_backend/app/routers` |
| 后端服务模块 | 235 | `nexus_backend/app/services` |
| Agent 工具模块 | 68 | `nexus_backend/app/tools` |
| 正向 SQL 迁移 | 145 | `supabase/migrations/*.sql` |
| 回滚 SQL | 13 | `supabase/migrations/rollback` |
| 强制生产聊天模型 | `deepseek-v4.1-flash` | `nexus_backend/app/core/config.py` |

## 前端最大文件

这些文件是渐进拆分清单，不代表可以无测试地批量重写。

| 文件 | 行数 |
|---|---:|
| `src/pages/OACenter.tsx` | 1255 |
| `src/lib/animations.ts` | 1185 |
| `src/pages/crm/CustomerDetailSheet.tsx` | 1101 |
| `src/pages/LLMModelManagement.tsx` | 1051 |
| `src/pages/OrgChartPage.tsx` | 991 |
| `src/pages/BattlecardLibrary.tsx` | 943 |
| `src/pages/FinanceCenter.tsx` | 805 |
| `src/pages/ContractManagement.tsx` | 750 |
| `src/pages/AgentDebugPanel.tsx` | 739 |
| `src/pages/TrainingCenter.tsx` | 731 |

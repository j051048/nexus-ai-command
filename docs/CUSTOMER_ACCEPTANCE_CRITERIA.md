# 小型企业客户验收标准

本标准适用于 20-50 人科学仪器企业的默认首发。首发目标是尽快跑通可量化业务闭环，不要求客户一次性接管所有横向模块。

## 默认首发范围（Default Launch Profile）

环境配置：`VITE_LAUNCH_PROFILE=small_company`。

`src/config/featureFlags.ts` 是模块范围的唯一权威来源。当前默认模块为：

- CRM、销售、客户与项目。
- 企业资料与知识检索。
- 竞品战卡、VMD、方案作战与投标作战。
- 审批、项目和报表。

财务、HR、OA、库存、资产、计费、插件、表单和工作流设计器属于按需模块或集成能力，不应作为默认首发通过条件。客户确有需求时使用 `extended` 或明确的模块覆盖配置，并单独指定 owner 与验收用例。

## 验收规则（Acceptance Rules）

1. 用户登录后只能进入所属组织，普通员工不能访问老板/平台管理页面。
2. 客户可创建、查看并维护需求、预算、行业、地域、仪器谱系和下一步动作。
3. 企业资料支持上传、去重、异步入库、状态查询、失败重试、质量审核和组织级可见性。
4. AI 能按文件名和业务语义检索指定资料，并返回文档身份、证据片段和待核验缺口。
5. 方案作战覆盖客户事实、需求、证据、配置、撰写、复核和交付；投标作战覆盖否决项、技术偏离、评分点、应答和定稿检查。
6. “制作精品成果”会重新检索企业资料并创建持久化任务，不把聊天文本直接包装成最终文件。
7. 成果质量门检查结构、字数、证据、语义、格式、安全和外部承诺；未通过时只标记为审核草稿。
8. 已完成成果能从当前页面及全局成果中心下载，至少验证 DOCX 和 PDF，适用场景再验证 XLSX/PNG。
9. AI 写操作通过 Tool RBAC、租户校验、幂等、审计和必要的 HITL；高风险动作不能由模型自行确认。
10. 失败状态提供可恢复操作，资料、任务和成果不能因刷新或切换页面而丢失。

## 自动化证据

| 证据 | 覆盖范围 |
|---|---|
| `python scripts/customer_acceptance_gate.py` | 模块、路由、后端 owner、安全契约和业务 E2E 静态检查 |
| `e2e/customer-business-acceptance.spec.ts` | 登录、CRM、审批、资料检索、角色边界、业务黄金路径和成果下载 |
| `e2e/solution-workspace.spec.ts` | 方案六阶段工作区与移动端 |
| `e2e/tender-workspace.spec.ts` | 投标六阶段工作区与兼容入口 |
| `python scripts/production_proof_gate.py` | Agent、Schema、RLS、成本、质量和交付契约 |
| `python scripts/run_customer_golden_acceptance.py --require-live` | 真实上传、入库、深度成果任务及 DOCX/PDF 下载 |

静态脚本通过只证明代码契约存在。在线验收必须配置专用测试组织：

```bash
GOLDEN_ACCEPTANCE_BASE_URL=https://api.example.com \
GOLDEN_ACCEPTANCE_TOKEN=... \
GOLDEN_ACCEPTANCE_ORG_ID=... \
python scripts/run_customer_golden_acceptance.py --require-live
```

## 交付退出条件

- `python scripts/check_handover_readiness.py`、`customer_acceptance_gate.py`、`release_quality_gate.py` 和 `production_proof_gate.py` 全部通过。
- `npm run quality:frontend`、前端覆盖率趋势门禁和核心 Playwright 套件通过。
- 空库迁移重放、Schema convergence、RLS coverage/policy scanner 通过；生产迁移已留存执行记录。
- 生产 `/health`、受保护深度健康检查和 `/api/system/deployment-health` 正常。
- 在线客户黄金验收通过，下载文件可打开且不包含其他租户数据、内部工具标记或未确认承诺。
- 管理员收到启用模块、凭据 owner、备份/恢复、Agent 降级、成本阈值、已知限制和回滚说明。
- 客户代表以真实资料完成一次方案或投标交付并签字确认，而非只观看演示数据。

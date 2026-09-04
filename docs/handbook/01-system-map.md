# 系统与领域地图

## 产品主线

| 领域 | 核心用户价值 | 主要入口 | 状态 |
|---|---|---|---|
| Growth/VMD | 科学仪器线索、客户、竞品、跟进与经营复盘 | `VMDCenter`、CRM、Battlecards | 商业主线 |
| Solution & Tender | 客户需求、三档配置、投标审阅、质量复核和文件交付 | `/growth/solutions`、`/growth/tenders`、成果中心 | 商业主线 |
| Agent Platform | 对话、计划、工具、记忆、评估 | `app/agent`、`app/tools` | 平台核心 |
| Enterprise Core | 组织、审批、合同、项目、通知 | 对应 routers/services | 稳定维护 |
| Enterprise Knowledge | 企业文档、入库、混合检索、证据包和关系洞察 | `/knowledge`、Documents、RAG | 核心支撑 |
| Artifact Quality | 深度生成、语义评审、格式渲染、版本和反馈 | `app/services/artifact_*`、`/artifact-quality` | 交付底盘 |
| Integrations | IM、支付、ERP、Webhooks | adapters/routers | 按客户启用 |
| Admin & Trust | 会员、配额、审计、SLO、成本 | super admin/Agent Ops | 运营底盘 |

## 依赖方向

`page/router -> hook/service -> domain/repository -> database`。Agent 通过工具目录调用领域服务；禁止 Agent 节点直接拼接任意表查询。领域间同步协作优先使用明确用例，异步副作用使用事件总线/Celery。

默认 `small_company` 首发范围由 `src/config/featureFlags.ts` 定义。当前核心是 CRM、审批、企业资料/知识、项目、报表、销售、竞品战卡、投标和 VMD；HR、财务、OA、库存、资产和计费优先作为按需模块或第三方集成，不应重新成为默认导航主线。

## 渐进拆分策略

- 不进行全仓“一次性 DDD 搬家”。
- 新功能先进入正确领域；改旧功能时才顺带迁移其边界。
- `app/domains/DOMAIN_REGISTRY` 用于防止同一路由或服务被多个领域认领。
- 大页面先抽离可独立测试的对话框、分区和 Hook，页面仍保留装配职责。

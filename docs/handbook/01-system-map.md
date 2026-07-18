# 系统与领域地图

## 产品主线

| 领域 | 核心用户价值 | 主要入口 | 状态 |
|---|---|---|---|
| Growth/VMD | 科学仪器线索、竞品、投标、跟进作战 | `VMD*`、CRM、Tender | 商业主线 |
| Agent Platform | 对话、计划、工具、记忆、评估 | `app/agent`、`app/tools` | 平台核心 |
| Enterprise Core | 组织、审批、合同、项目、通知 | 对应 routers/services | 稳定维护 |
| Data & Knowledge | 文档、RAG、关系图谱、报表 | Knowledge/Reports | 核心支撑 |
| Integrations | IM、支付、ERP、Webhooks | adapters/routers | 按客户启用 |
| Admin & Trust | 会员、配额、审计、SLO、成本 | super admin/Agent Ops | 运营底盘 |

## 依赖方向

`page/router -> hook/service -> domain/repository -> database`。Agent 通过工具目录调用领域服务；禁止 Agent 节点直接拼接任意表查询。领域间同步协作优先使用明确用例，异步副作用使用事件总线/Celery。

## 渐进拆分策略

- 不进行全仓“一次性 DDD 搬家”。
- 新功能先进入正确领域；改旧功能时才顺带迁移其边界。
- `app/domains/DOMAIN_REGISTRY` 用于防止同一路由或服务被多个领域认领。
- 大页面先抽离可独立测试的对话框、分区和 Hook，页面仍保留装配职责。

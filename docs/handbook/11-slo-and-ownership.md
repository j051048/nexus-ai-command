# SLO 与所有权

## 初始服务目标

| 指标 | 目标 | Owner |
|---|---:|---|
| 核心 API 可用性 | 99.9% / 月 | Backend/SRE |
| 核心 API P95 | < 800 ms（不含长 Agent） | Backend |
| Agent 首个可见状态 P95 | < 1 s | Agent + Frontend |
| 关键 Agent 完成率 | > 95% | Agent |
| 高风险错误执行 | 0 | Security + Domain |
| 跨租户数据泄露 | 0 | Security + Data |
| 队列最老任务 | < 5 min | SRE |

SLO 是初始值，应在获得真实流量后按场景拆分。错误预算耗尽时暂停非必要功能发布，优先处理可靠性。

## 责任矩阵

- **Frontend**：页面、设计系统、Web Vitals、SSE 消费与无障碍。
- **Backend**：API、领域事务、任务幂等与集成适配。
- **Agent**：路由、prompt/context、工具目录、eval 和成本。
- **Data/Security**：迁移、RLS、审计、备份、隐私和事故响应。
- **Product/Domain**：验收标准、领域数据集、HITL 边界和 ROI。

当前 CODEOWNERS 使用临时维护者兜底；团队接管后的第一个治理 PR 应替换为真实团队别名。

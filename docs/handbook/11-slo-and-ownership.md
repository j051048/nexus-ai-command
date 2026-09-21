# SLO 与所有权

## 初始服务目标

| 指标 | 目标 | Owner |
|---|---:|---|
| 核心 API 可用性 | 99.9% / 月 | Backend/SRE |
| 核心 API P95 | < 800 ms（不含长 Agent） | Backend |
| Agent 首个可见状态 P95 | < 1 s | Agent + Frontend |
| 关键 Agent 完成率 | > 95% | Agent |
| 企业资料入库成功率 | > 99% | Knowledge + SRE |
| 精品成果任务完成率 | > 95% | Agent + Delivery |
| 可交付成果证据覆盖率 | > 90%（按已声明关键事实） | Agent + Domain |
| 已完成成果下载成功率 | > 99% | Backend + SRE |
| 高风险错误执行 | 0 | Security + Domain |
| 跨租户数据泄露 | 0 | Security + Data |
| 队列最老任务 | < 5 min | SRE |

SLO 是初始值，应在获得真实流量后按场景拆分。错误预算耗尽时暂停非必要功能发布，优先处理可靠性。

## 文档交付质量 SLO

成果文件（方案、标书、报告）的验收口径由 `app/services/artifact_quality_slo.py` 固化，看板在 `/artifact-quality`（管理员），月度报告接口为 `GET /api/artifact-quality/monthly-report`。

| 指标 | 目标 | 计算口径 | Owner |
|---|---:|---|---|
| 一次通过率 `ready_rate` | ≥ 90% | 近 N 天 `agent_artifact_quality_events` 中 `ready=true` 占比 | Delivery + Domain |
| 平均质量分 `avg_score` | ≥ 85 | 规则分与 LLM 评审分的加权平均（外发 0.5/0.5，内部 0.6/0.4） | Agent + Domain |
| 平均证据覆盖 `avg_evidence_coverage` | ≥ 90% | 已声明关键事实中可溯源的比例 | Knowledge + Domain |
| LLM 评审维度下限 | ≥ 70（参考线） | 证据忠实度、客户价值、逻辑连贯、语言专业度 | Agent + Domain |
| 返工次数 `avg_repair_count` | 只降不升 | 每次交付的平均自动修复轮次 | Agent |

口径说明：

- 三项 SLO 中任一项低于目标即整体 `warn`，不隐藏失败原因；
- LLM 评审为 best-effort，不可用时降级为确定性结论，因此维度下限不是 SLO，只用于定位质量是在哪个维度下滑；
- 样本量为 0 时返回 `available=false`，不得当作达标；
- 客户赢单/输单通过 `POST /api/artifact-quality/outcomes` 回流，并折算进模板 A/B 排序与晋升门槛。

## 责任矩阵

- **Frontend**：页面、设计系统、Web Vitals、SSE 消费与无障碍。
- **Backend**：API、领域事务、任务幂等与集成适配。
- **Agent**：路由、prompt/context、工具目录、eval 和成本。
- **Knowledge/Delivery**：资料入库、检索、证据契约、成果模板、质量门和下载生命周期。
- **Data/Security**：迁移、RLS、审计、备份、隐私和事故响应。
- **Product/Domain**：验收标准、领域数据集、HITL 边界和 ROI。

当前 CODEOWNERS 使用临时维护者兜底；团队接管后的第一个治理 PR 应替换为真实团队别名。

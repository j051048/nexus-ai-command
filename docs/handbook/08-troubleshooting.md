# 故障排查

| 现象 | 首查 | 常见原因 |
|---|---|---|
| 全站 404/Not Found 提示 | 浏览器 Network、API base URL | 路由未注册、前后端版本不匹配 |
| 作战数据不可用 | dashboard 请求与后端日志 | 迁移未执行、RLS/字段契约漂移 |
| Agent 长时间无输出 | SSE、Agent run、worker 队列 | 网关超时、工具阻塞、worker 不在线 |
| 页面能看到资料但 AI 说未找到 | 文档 ingestion 状态、`document_id`、组织上下文、检索证据 | 入库未完成、名称召回缺失、选择的资料不属于当前组织 |
| “制作精品成果”无反应 | `/api/artifacts/jobs`、浏览器 Network、成果任务健康 | 前后端版本不匹配、成果路由未部署、Worker/后台任务不可用 |
| 成果生成后找不到或不能下载 | 右上角成果中心、artifact 状态和 download 响应 | 任务仍在运行、质量门仅允许草稿、存储/权限或组织绑定错误 |
| 自动任务重复执行 | Beat、分布式锁、任务幂等键 | 多 Pod 各自调度 |
| 跨租户异常 | auth context、RLS policy | service key 误用、缺少对象归属校验 |
| LLM 成本突增 | 模型成本看板、scene/agent | 绕过网关、反思循环、上下文膨胀 |
| `获取配置失败: 'NoneType' object has no attribute 'data'` | `app/core/postgrest_compat.py` 是否被删 | `maybe_single()` 零行契约回归：postgrest-py ≥0.16 命中零行时返回 `None` 而不是空响应，约 150 处调用点会崩 |
| `AI execution policy unavailable; using safe defaults` | 上面那一行是否同时出现 | 同源：策略行不存在时 `get_config` 崩溃被上层吞掉，租户静默降级到安全默认策略 |
| `Token budget check failed ... Redis URL must specify one of the following schemes` | `REDIS_URL` 取值（不要贴密码） | 值不是 `redis://` / `rediss://` / `unix://`；云端控制台常只给 `host:port`。`app/core/redis_url.py` 会补前缀，其余非法值按"未配置 Redis"降级 |
| `No DB config found for model=..., using env fallback config` | `llm_model_config` 是否有该 `model_code` 的行 | 数据缺口而非代码缺陷：`FORCED_CHAT_MODEL` 指向的模型在库里没有 enabled 行，网关按设计退回 env 配置 |

排查顺序：确认影响范围 -> 关联 `trace_id` -> 检查最近发布/迁移 -> 降级或回滚 -> 保留证据 -> 复盘并增加回归测试。不要在事故中直接修改历史迁移。

知识与成果问题还应记录 `organization_id`、`document_id`、`artifact_id/job_id`、选用资料、检索证据数量和质量失败码；不要只保存前端截图。

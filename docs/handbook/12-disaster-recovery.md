# 灾难恢复演练

每季度至少演练一次数据库时间点恢复、Redis/Worker 中断、LLM Provider 故障和错误迁移。

## 备份分层与执行者

两层备份，各自有明确的执行者，缺一层都不算具备恢复能力。

| 层 | 执行者 | 存放位置 | 覆盖的故障 |
|---|---|---|---|
| 数据库快照 | `scripts/backup_supabase.{sh,ps1}`（pg_dump，由平台/运维调度） | 对象存储或离线介质 | 主库损坏、误迁移、区域故障 |
| 应用级组织备份 | `app/tasks/backup_tasks.py`（Celery Beat，每 15 分钟扫描） | 由 `BACKUP_STORAGE_BACKEND` 决定，默认仍写 `backup_records.data` | 组织级误删、单租户数据回滚 |

应用级备份的执行链路：

1. Beat 触发 `run_due_backup_schedules`，按 `next_backup_at` 领取到期计划；
2. 领取是对 `next_backup_at` 的比较并交换（CAS），多副本同时触发时只有一个副本执行该组织；
3. 备份负载按 `BACKUP_STORAGE_BACKEND` 写入数据库、文件系统或 S3 兼容对象存储，记录 `storage_backend`、`storage_ref` 与 `checksum`；
4. 写后校验：外部存储比对 `checksum`，数据库后端核对表集合与行数，结果写入 `verified_at`；
5. 单组织失败只标记该计划 `last_status='failed'` 与 `last_error`，不中断同批其他组织。

因此 `backup_schedules` 里设置的计划会被真正执行；`BACKUP_STORAGE_BACKEND` 不是默认值时，数据库只保留清单与校验和，主库损坏不会再连带备份一起丢。

## 数据保留执行

`GET /api/compliance/retention` 报告的窗口由 `app/tasks/retention_tasks.py` 执行（每天 05:00）。默认 `DATA_RETENTION_ENFORCEMENT_ENABLED=false`，此时接口返回 `enforcement_enabled=false`，不会声称策略正在生效。

开启后按组织逐个执行删除：每个删除批次都绑定单一 `organization_id`，一个租户的异常数据不会扩大影响面；每次清理写入 `data_retention_runs`（data_type、窗口、cutoff、删除行数、状态），接口的 `last_runs` 即来自该表。

已知边界：`audit_logs` 中 `org_id IS NULL` 的平台级审计行不属于任何租户，不参与按组织清理，需要平台 owner 单独处理。

## 演练步骤

1. 记录 RPO/RTO 目标与演练开始时间。
2. 在隔离环境恢复最近备份并校验租户、审计和向量数据。
3. 重放幂等任务，验证不会重复外发或重复扣费。
4. 切换 LLM 降级模式，确认高风险动作仍需人工确认。
5. 运行黄金路径与 RLS 隔离测试。
6. 记录实际 RPO/RTO、缺失证据和整改 owner。

数据库恢复成功但业务不变量失效，不算演练通过。

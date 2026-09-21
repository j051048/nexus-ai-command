-- ============================================================
-- 备份执行者与数据保留执行
--
-- 背景：backup_schedules 只被写入、从未被读取，backup_records.expires_at
-- 从未回收，/api/compliance/retention 声明的保留期也没有对应清理任务。
-- 本迁移补齐这些能力所需的存储：异地存放位置、完整性证据、调度执行结果
-- 与保留清理审计。
-- ============================================================

-- 1) backup_records：记录负载实际存放位置与完整性证据
ALTER TABLE backup_records
    ADD COLUMN IF NOT EXISTS storage_backend TEXT NOT NULL DEFAULT 'database';
ALTER TABLE backup_records
    ADD COLUMN IF NOT EXISTS storage_ref TEXT;
ALTER TABLE backup_records
    ADD COLUMN IF NOT EXISTS checksum TEXT;
ALTER TABLE backup_records
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;

-- 2) backup_schedules：记录执行结果，让失败在数据库里可见
ALTER TABLE backup_schedules
    ADD COLUMN IF NOT EXISTS last_status TEXT;
ALTER TABLE backup_schedules
    ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE backup_schedules
    ADD COLUMN IF NOT EXISTS last_backup_id UUID REFERENCES backup_records(id) ON DELETE SET NULL;
ALTER TABLE backup_schedules
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ;

-- 3) 到期扫描索引
CREATE INDEX IF NOT EXISTS idx_backup_records_expires_at
    ON backup_records(expires_at) WHERE expires_at IS NOT NULL;

-- 4) backup_records 需要 UPDATE 权限才能回写 verified_at
--    （原迁移只授予 SELECT/INSERT/DELETE，校验结果会静默丢弃）
DROP POLICY IF EXISTS "backup_records_update_admin" ON backup_records;
CREATE POLICY "backup_records_update_admin" ON backup_records
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid() AND role IN ('founder', 'boss')
        )
    )
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid() AND role IN ('founder', 'boss')
        )
    );

-- 5) 数据保留清理审计
--    该表是平台级运维记录（不含 organization_id），因此只对 service_role
--    开放，避免暴露跨租户的清理量。
CREATE TABLE IF NOT EXISTS public.data_retention_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_type TEXT NOT NULL,
    retention_days INTEGER NOT NULL,
    cutoff TIMESTAMPTZ NOT NULL,
    deleted_rows INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'completed'
        CHECK (status IN ('completed', 'failed', 'skipped')),
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_data_retention_runs_type
    ON public.data_retention_runs(data_type, started_at DESC);

ALTER TABLE public.data_retention_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "data_retention_runs_service" ON public.data_retention_runs;
CREATE POLICY "data_retention_runs_service" ON public.data_retention_runs
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

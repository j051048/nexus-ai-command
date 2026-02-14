-- ============================================================
-- 灾备与数据恢复 - 备份记录和备份调度表
-- ============================================================

-- 备份记录表
CREATE TABLE IF NOT EXISTS backup_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    backup_type TEXT DEFAULT 'manual' CHECK (backup_type IN ('manual', 'auto', 'pre_restore')),
    tables_included TEXT[] NOT NULL,
    data JSONB NOT NULL,
    size_bytes BIGINT,
    status TEXT DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed')),
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- 备份调度表
CREATE TABLE IF NOT EXISTS backup_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) UNIQUE,
    frequency TEXT DEFAULT 'daily' CHECK (frequency IN ('daily', 'weekly', 'monthly')),
    tables TEXT[] DEFAULT ARRAY['users', 'approval_requests', 'documents'],
    is_active BOOLEAN DEFAULT true,
    last_backup_at TIMESTAMPTZ,
    next_backup_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_backup_records_org_id ON backup_records(organization_id);
CREATE INDEX IF NOT EXISTS idx_backup_records_created_at ON backup_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backup_records_type ON backup_records(backup_type);
CREATE INDEX IF NOT EXISTS idx_backup_schedules_next ON backup_schedules(next_backup_at) WHERE is_active = true;

-- ============================================================
-- RLS 策略
-- ============================================================

ALTER TABLE backup_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE backup_schedules ENABLE ROW LEVEL SECURITY;

-- backup_records: 组织成员可读取本组织的备份记录
CREATE POLICY "backup_records_select_org" ON backup_records
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- backup_records: 仅管理员可创建备份
CREATE POLICY "backup_records_insert_admin" ON backup_records
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid() AND role IN ('admin', 'founder', 'boss')
        )
    );

-- backup_records: 仅管理员可删除（清理过期备份）
CREATE POLICY "backup_records_delete_admin" ON backup_records
    FOR DELETE
    USING (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid() AND role IN ('admin', 'founder', 'boss')
        )
    );

-- backup_schedules: 组织成员可查看
CREATE POLICY "backup_schedules_select_org" ON backup_schedules
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- backup_schedules: 管理员可管理调度
CREATE POLICY "backup_schedules_all_admin" ON backup_schedules
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid() AND role IN ('admin', 'founder', 'boss')
        )
    );

-- 为 service key 提供完整访问（超级管理员和后台任务）
CREATE POLICY "backup_records_service" ON backup_records
    FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "backup_schedules_service" ON backup_schedules
    FOR ALL
    USING (auth.role() = 'service_role');

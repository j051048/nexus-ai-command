-- ============================================================
-- IM 平台深度集成数据库迁移
-- 企微/钉钉/飞书: 用户映射、考勤记录、平台配置
-- ============================================================

-- ── IM 用户映射表 ───────────────────────────────────────────
-- 存储 Nexus 用户与 IM 平台用户的映射关系
CREATE TABLE IF NOT EXISTS im_user_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('wecom', 'dingtalk', 'feishu')),
    platform_user_id TEXT NOT NULL,
    platform_username TEXT,
    platform_department_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, platform, platform_user_id)
);

COMMENT ON TABLE im_user_mappings IS 'IM 平台用户映射表 - 关联 Nexus 用户与企微/钉钉/飞书用户';
COMMENT ON COLUMN im_user_mappings.platform IS '平台标识: wecom, dingtalk, feishu';
COMMENT ON COLUMN im_user_mappings.platform_user_id IS '平台侧用户 ID（如企微 userid、钉钉 userid、飞书 user_id）';
COMMENT ON COLUMN im_user_mappings.platform_username IS '平台侧用户名称（同步时更新）';
COMMENT ON COLUMN im_user_mappings.platform_department_id IS '平台侧部门 ID（最后一次同步的部门）';

-- ── 考勤记录表 ──────────────────────────────────────────────
-- 从 IM 平台同步的考勤打卡数据
CREATE TABLE IF NOT EXISTS attendance_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('wecom', 'dingtalk', 'feishu')),
    check_date DATE NOT NULL,
    check_in_time TIMESTAMPTZ,
    check_out_time TIMESTAMPTZ,
    status TEXT DEFAULT 'normal' CHECK (status IN ('normal', 'late', 'early_leave', 'absent', 'overtime')),
    location TEXT,
    raw_data JSONB,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, organization_id, platform, check_date)
);

COMMENT ON TABLE attendance_records IS '考勤记录表 - 从 IM 平台同步的打卡数据';
COMMENT ON COLUMN attendance_records.status IS '考勤状态: normal=正常, late=迟到, early_leave=早退, absent=旷工, overtime=加班';
COMMENT ON COLUMN attendance_records.raw_data IS '原始平台数据（用于审计和问题排查）';
COMMENT ON COLUMN attendance_records.synced_at IS '最后同步时间';

-- ── IM 平台配置表 ───────────────────────────────────────────
-- 存储各组织的 IM 平台连接配置（敏感字段建议应用层加密）
CREATE TABLE IF NOT EXISTS im_platform_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    platform TEXT NOT NULL CHECK (platform IN ('wecom', 'dingtalk', 'feishu')),
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, platform)
);

COMMENT ON TABLE im_platform_config IS 'IM 平台配置表 - 存储各组织的企微/钉钉/飞书连接信息';
COMMENT ON COLUMN im_platform_config.config IS '平台配置 JSON: wecom={corp_id, corp_secret, agent_id}, dingtalk={app_key, app_secret, agent_id}, feishu={app_id, app_secret}';
COMMENT ON COLUMN im_platform_config.is_active IS '是否启用该平台集成';

-- ── 部门表（如果不存在）─────────────────────────────────────
-- 通讯录同步时需要的部门表
CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    external_id TEXT,
    external_parent_id TEXT,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, external_id)
);

COMMENT ON TABLE departments IS '部门表 - 从 IM 平台同步的组织部门结构';

-- ── Row Level Security ──────────────────────────────────────

ALTER TABLE im_user_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE im_platform_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;

-- im_user_mappings: 按 organization_id 隔离
CREATE POLICY im_user_mappings_org_isolation
    ON im_user_mappings
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    )
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- attendance_records: 按 organization_id 隔离
CREATE POLICY attendance_records_org_isolation
    ON attendance_records
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    )
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- im_platform_config: 按 organization_id 隔离（仅管理员可管理）
CREATE POLICY im_platform_config_org_isolation
    ON im_platform_config
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid() AND role IN ('boss', 'founder')
        )
    )
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid() AND role IN ('boss', 'founder')
        )
    );

-- departments: 按 organization_id 隔离
CREATE POLICY departments_org_isolation
    ON departments
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    )
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- ── 索引 ────────────────────────────────────────────────────

-- 考勤记录: 按用户 + 日期查询
CREATE INDEX IF NOT EXISTS idx_attendance_user_date
    ON attendance_records (user_id, check_date);

-- 考勤记录: 按组织 + 日期查询
CREATE INDEX IF NOT EXISTS idx_attendance_org_date
    ON attendance_records (organization_id, check_date);

-- 考勤记录: 按状态筛选异常
CREATE INDEX IF NOT EXISTS idx_attendance_status
    ON attendance_records (organization_id, status)
    WHERE status != 'normal';

-- 用户映射: 按组织 + 平台查询
CREATE INDEX IF NOT EXISTS idx_im_mapping_org_platform
    ON im_user_mappings (organization_id, platform);

-- 用户映射: 按平台用户 ID 查询（OAuth 回调时使用）
CREATE INDEX IF NOT EXISTS idx_im_mapping_platform_userid
    ON im_user_mappings (platform, platform_user_id);

-- 平台配置: 按组织查询活跃配置
CREATE INDEX IF NOT EXISTS idx_im_config_org_active
    ON im_platform_config (organization_id, is_active)
    WHERE is_active = true;

-- 部门: 按组织查询
CREATE INDEX IF NOT EXISTS idx_departments_org
    ON departments (organization_id);

-- ── updated_at 自动更新触发器 ────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_im_user_mappings_updated_at
    BEFORE UPDATE ON im_user_mappings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_im_platform_config_updated_at
    BEFORE UPDATE ON im_platform_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_departments_updated_at
    BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

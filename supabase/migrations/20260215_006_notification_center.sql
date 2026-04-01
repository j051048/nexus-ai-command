-- ============================================================
-- Item 16: Notification Center + Preferences
-- In-app notification center with preference management
-- ============================================================

-- 通知表（增强现有 notifications 表结构，若已存在则添加缺失列）
-- 如果 notifications 表已存在，以下 CREATE TABLE 会跳过（IF NOT EXISTS）
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id),
    title TEXT NOT NULL,
    body TEXT,
    type TEXT DEFAULT 'info' CHECK (type IN ('info', 'success', 'warning', 'error', 'approval', 'system')),
    action_url TEXT,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 为现有 notifications 表安全地添加可能缺失的列
DO $$
BEGIN
    -- Add body column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'notifications' AND column_name = 'body'
    ) THEN
        ALTER TABLE notifications ADD COLUMN body TEXT;
    END IF;

    -- Add action_url column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'notifications' AND column_name = 'action_url'
    ) THEN
        ALTER TABLE notifications ADD COLUMN action_url TEXT;
    END IF;

    -- Add is_read column if not exists (some schemas use 'read' instead)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'notifications' AND column_name = 'is_read'
    ) THEN
        ALTER TABLE notifications ADD COLUMN is_read BOOLEAN DEFAULT false;
    END IF;

    -- Add organization_id column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'notifications' AND column_name = 'organization_id'
    ) THEN
        ALTER TABLE notifications ADD COLUMN organization_id UUID REFERENCES organizations(id);
    END IF;
END
$$;

-- 通知偏好表
CREATE TABLE IF NOT EXISTS notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    email_enabled BOOLEAN DEFAULT true,
    push_enabled BOOLEAN DEFAULT true,
    im_enabled BOOLEAN DEFAULT true,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    categories JSONB DEFAULT '{"approval": true, "system": true, "ai": true, "report": true}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- Drop existing policies to avoid conflicts, then recreate
DO $$
BEGIN
    DROP POLICY IF EXISTS "Users read own notifications" ON notifications;
    DROP POLICY IF EXISTS "Users update own notifications" ON notifications;
EXCEPTION WHEN OTHERS THEN
    NULL;
END
$$;

CREATE POLICY "Users read own notifications"
    ON notifications
    FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users update own notifications"
    ON notifications
    FOR UPDATE
    USING (user_id = auth.uid());

ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own notification preferences"
    ON notification_preferences
    FOR ALL
    USING (user_id = auth.uid());

-- Indexes
CREATE INDEX IF NOT EXISTS idx_notifications_user_read
    ON notifications(user_id, is_read);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created
    ON notifications(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_type
    ON notifications(user_id, type);

-- 工作流共享模板表（Item 12 依赖）
CREATE TABLE IF NOT EXISTS workflow_shared_templates (
    id TEXT PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'custom',
    applies_to JSONB DEFAULT '[]',
    steps JSONB DEFAULT '[]',
    conditions JSONB,
    usage_count INTEGER DEFAULT 0,
    shared_by UUID REFERENCES auth.users(id),
    source_workflow_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE workflow_shared_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Org members manage shared templates"
    ON workflow_shared_templates
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

CREATE INDEX IF NOT EXISTS idx_shared_templates_org
    ON workflow_shared_templates(organization_id, category);

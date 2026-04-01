-- 用户通知反馈记录表
CREATE TABLE IF NOT EXISTS user_notification_preferences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    notification_type text NOT NULL,
    action text NOT NULL,
    created_at timestamptz DEFAULT now(),
    CONSTRAINT valid_action CHECK (action IN ('clicked', 'dismissed', 'ignored', 'muted'))
);

CREATE INDEX idx_unp_user_type ON user_notification_preferences(user_id, notification_type);
CREATE INDEX idx_unp_created ON user_notification_preferences(created_at);

-- 用户偏好配置表
CREATE TABLE IF NOT EXISTS user_preference_settings (
    user_id uuid PRIMARY KEY,
    active_hours_start int DEFAULT 9,
    active_hours_end int DEFAULT 18,
    daily_notification_limit int DEFAULT 5,
    muted_types text[] DEFAULT '{}',
    updated_at timestamptz DEFAULT now()
);

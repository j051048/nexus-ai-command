-- P2: 统一日历事件表 + 冲突检测函数
-- 解决日程数据分散在 oa_leave_requests, oa_meeting_bookings, oa_tasks, user_scheduled_tasks 等多张表的问题

-- 1. calendar_events 表：统一的日程存储
CREATE TABLE IF NOT EXISTS calendar_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'meeting', 'leave', 'task_deadline', 'scheduled_task', 'travel', 'custom'
    )),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,             -- NULL for point events / all-day without explicit end
    all_day BOOLEAN DEFAULT FALSE,
    source_table TEXT,                -- 来源表: oa_meeting_bookings, oa_leave_requests, etc.
    source_id UUID,                   -- 来源记录ID
    attendees TEXT[] DEFAULT '{}',    -- 参会人姓名
    location TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'completed')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_calendar_events_user_time
    ON calendar_events(user_id, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source
    ON calendar_events(source_table, source_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_org
    ON calendar_events(organization_id) WHERE organization_id IS NOT NULL;

-- RLS
ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own calendar events"
    ON calendar_events FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access on calendar_events"
    ON calendar_events FOR ALL
    USING (auth.role() = 'service_role');

-- 2. 冲突检测 RPC: 查询指定时段内的冲突事件
CREATE OR REPLACE FUNCTION check_calendar_conflicts(
    p_user_id UUID,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ,
    p_exclude_id UUID DEFAULT NULL
)
RETURNS TABLE(
    id UUID,
    title TEXT,
    event_type TEXT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ
)
LANGUAGE SQL STABLE
AS $$
    SELECT ce.id, ce.title, ce.event_type, ce.start_time, ce.end_time
    FROM calendar_events ce
    WHERE ce.user_id = p_user_id
      AND ce.status = 'active'
      AND (p_exclude_id IS NULL OR ce.id != p_exclude_id)
      AND ce.start_time < p_end_time
      AND (ce.end_time IS NULL OR ce.end_time > p_start_time)
    ORDER BY ce.start_time
    LIMIT 10;
$$;

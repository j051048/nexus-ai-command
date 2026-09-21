-- ============================================================
-- SLO 告警台账
--
-- 背景：SLO 有目标、指标有埋点，但越界时只写一行日志，没有人会收到通知。
-- 本表记录每次告警的投递与恢复，让告警可以按 key 去重（重启后不会重复打扰），
-- 并留下"何时告警、何时恢复、是否投递成功"的证据。
--
-- 该表是平台级运维台账：去重 key 是全局的，仅对 service_role 开放，
-- 任何租户侧请求都读不到它。
-- ============================================================

CREATE TABLE IF NOT EXISTS public.ops_alert_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key TEXT NOT NULL UNIQUE,
    severity TEXT NOT NULL DEFAULT 'warning'
        CHECK (severity IN ('warning', 'critical')),
    title TEXT NOT NULL,
    detail TEXT,
    source TEXT NOT NULL,
    organization_id UUID,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    delivered BOOLEAN NOT NULL DEFAULT FALSE,
    send_count INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_ops_alert_events_open
    ON public.ops_alert_events(last_sent_at DESC) WHERE resolved_at IS NULL;

ALTER TABLE public.ops_alert_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ops_alert_events_service" ON public.ops_alert_events;
CREATE POLICY "ops_alert_events_service" ON public.ops_alert_events
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

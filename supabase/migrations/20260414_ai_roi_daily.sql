-- AI ROI Daily Metrics & Baselines
-- Aggregated daily metrics for measuring AI investment return

-- ── ai_roi_daily ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ai_roi_daily (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id   text NOT NULL,
    metric_date date NOT NULL,

    -- Cost
    ai_cost_usd        numeric(12,4) NOT NULL DEFAULT 0,
    total_tokens        bigint NOT NULL DEFAULT 0,
    total_llm_calls     integer NOT NULL DEFAULT 0,

    -- Tool execution
    tool_calls_total    integer NOT NULL DEFAULT 0,
    tool_calls_success  integer NOT NULL DEFAULT 0,

    -- Action category counts (from tool_execution_audit)
    cat_approval        integer NOT NULL DEFAULT 0,
    cat_crm             integer NOT NULL DEFAULT 0,
    cat_report          integer NOT NULL DEFAULT 0,
    cat_attendance      integer NOT NULL DEFAULT 0,
    cat_finance         integer NOT NULL DEFAULT 0,
    cat_leave           integer NOT NULL DEFAULT 0,
    cat_schedule        integer NOT NULL DEFAULT 0,
    cat_knowledge       integer NOT NULL DEFAULT 0,
    cat_other           integer NOT NULL DEFAULT 0,

    -- Derived savings
    estimated_minutes_saved   numeric(10,1) NOT NULL DEFAULT 0,
    estimated_labor_cost_saved numeric(12,2) NOT NULL DEFAULT 0,
    roi_percent               numeric(8,2)  NOT NULL DEFAULT 0,

    -- Quality
    avg_response_time_ms  integer NOT NULL DEFAULT 0,
    positive_feedback     integer NOT NULL DEFAULT 0,
    negative_feedback     integer NOT NULL DEFAULT 0,

    created_at  timestamptz DEFAULT now(),

    CONSTRAINT uq_roi_daily UNIQUE (tenant_id, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_roi_daily_tenant_date
    ON public.ai_roi_daily (tenant_id, metric_date DESC);

-- ── ai_roi_baselines ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ai_roi_baselines (
    id                uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    action_category   text NOT NULL UNIQUE,
    baseline_minutes  numeric(6,1) NOT NULL DEFAULT 10,
    hourly_labor_cost numeric(8,2) NOT NULL DEFAULT 50,
    description       text,
    updated_at        timestamptz DEFAULT now()
);

-- Default baselines (人工完成同样操作的平均耗时 & 时薪)
INSERT INTO public.ai_roi_baselines (action_category, baseline_minutes, hourly_labor_cost, description) VALUES
    ('approval',   15,  50, '审批流程：查看详情→判断→操作→通知'),
    ('crm',        20,  50, 'CRM操作：客户查询→跟进记录→状态更新'),
    ('report',     60,  60, '报告生成：数据收集→分析→撰写→审阅'),
    ('attendance',  5,  40, '考勤操作：查询→核实→处理异常'),
    ('finance',    30,  55, '财务操作：单据核对→录入→审批流转'),
    ('leave',      10,  40, '请假流程：填写申请→提交→等待审批'),
    ('schedule',   10,  40, '日程管理：查看安排→协调→创建事件'),
    ('knowledge',  15,  50, '知识库检索：搜索→阅读→整理→回复'),
    ('other',       8,  45, '其他操作：通用任务处理')
ON CONFLICT (action_category) DO NOTHING;

-- ── RLS ──────────────────────────────────────────────────────────────────────
ALTER TABLE public.ai_roi_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_roi_baselines ENABLE ROW LEVEL SECURITY;

-- ai_roi_daily: users can only see their org's data
CREATE POLICY "roi_daily_tenant_isolation" ON public.ai_roi_daily
    FOR SELECT USING (
        tenant_id = (SELECT raw_app_meta_data->>'org_id' FROM auth.users WHERE id = auth.uid())
    );

-- ai_roi_baselines: read-only for all authenticated users
CREATE POLICY "roi_baselines_read" ON public.ai_roi_baselines
    FOR SELECT USING (auth.role() = 'authenticated');

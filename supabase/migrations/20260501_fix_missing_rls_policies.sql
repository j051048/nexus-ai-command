-- P0-1 Security Fix: 补全 RLS 策略 — oa_meeting_rooms, oa_work_handovers, vmd_sub_task
-- 由 scripts/scan_rls_coverage.py 扫描发现的遗漏
-- 执行时间: 2026-05-01

-- ============================================================
-- 1. oa_meeting_rooms — 会议室资源
-- ============================================================
ALTER TABLE public.oa_meeting_rooms ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation_select" ON public.oa_meeting_rooms
  FOR SELECT USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_insert" ON public.oa_meeting_rooms
  FOR INSERT WITH CHECK (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_update" ON public.oa_meeting_rooms
  FOR UPDATE USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_delete" ON public.oa_meeting_rooms
  FOR DELETE USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

-- ============================================================
-- 2. oa_work_handovers — 工作交接记录
-- ============================================================
ALTER TABLE public.oa_work_handovers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation_select" ON public.oa_work_handovers
  FOR SELECT USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_insert" ON public.oa_work_handovers
  FOR INSERT WITH CHECK (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_update" ON public.oa_work_handovers
  FOR UPDATE USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_delete" ON public.oa_work_handovers
  FOR DELETE USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

-- ============================================================
-- 3. vmd_sub_task — VMD 子任务
-- ============================================================
ALTER TABLE public.vmd_sub_task ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation_select" ON public.vmd_sub_task
  FOR SELECT USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_insert" ON public.vmd_sub_task
  FOR INSERT WITH CHECK (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_update" ON public.vmd_sub_task
  FOR UPDATE USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_delete" ON public.vmd_sub_task
  FOR DELETE USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

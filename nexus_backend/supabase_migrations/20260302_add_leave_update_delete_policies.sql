-- Fix: oa_leave_requests 表缺少 UPDATE 和 DELETE 的 RLS 策略
-- 导致前端调用 supabase.update({status:'cancelled'}) 静默失败（0行受影响，不报错）
-- 用户撤回请假后刷新页面记录会重新出现

-- 1. 允许用户更新自己的请假记录（撤回/取消）
DROP POLICY IF EXISTS "Users can update own leave requests" ON oa_leave_requests;
CREATE POLICY "Users can update own leave requests" ON oa_leave_requests
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 2. 允许管理员(founder)更新所有请假记录（审批）
DROP POLICY IF EXISTS "Managers can update all leave requests" ON oa_leave_requests;
CREATE POLICY "Managers can update all leave requests" ON oa_leave_requests
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.role = 'founder'
        )
    );

-- 3. 允许用户删除自己的请假记录（可选，以防未来需要硬删除）
DROP POLICY IF EXISTS "Users can delete own leave requests" ON oa_leave_requests;
CREATE POLICY "Users can delete own leave requests" ON oa_leave_requests
    FOR DELETE
    USING (auth.uid() = user_id);

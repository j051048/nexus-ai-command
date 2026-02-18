-- ============================================
-- Beta 测试准备：清理种子假数据
-- 日期: 2026-02-18
-- 说明: 删除开发阶段插入的假用户、假线索、假审批、假激励数据
--       保留系统初始化数据(会议室、部门、审批链)
-- ============================================

-- 1. 删除 seed_data.sql 插入的 3 个假用户
DELETE FROM public.users
WHERE id IN (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13'
);

-- 2. 显式清理可能残留的关联数据
DELETE FROM public.sales_leads
WHERE owner_id IN (
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13'
);

DELETE FROM public.approval_requests
WHERE submitted_by IN (
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13'
);

DELETE FROM public.incentives
WHERE user_id IN (
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13'
);

-- 3. 清理 2024 年假预算数据
DELETE FROM public.finance_budgets
WHERE year = 2024;

-- 4. 清理无组织归属的 sales_metrics
DELETE FROM public.sales_metrics
WHERE organization_id IS NULL;

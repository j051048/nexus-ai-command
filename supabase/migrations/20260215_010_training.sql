-- ============================================
-- AI 培训助手: 数据库迁移
-- Version: 20260215_010
-- Description: training_progress 表, RLS 策略
-- ============================================

-- ============================================
-- 1. 创建 training_progress 表
-- ============================================
CREATE TABLE IF NOT EXISTS public.training_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES public.organizations(id),
    course_id TEXT NOT NULL,
    module_id TEXT NOT NULL,
    completed BOOLEAN DEFAULT false,
    score FLOAT,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, course_id, module_id)
);

-- 索引：按用户查询
CREATE INDEX IF NOT EXISTS idx_training_progress_user
    ON public.training_progress(user_id);

-- 索引：按课程查询
CREATE INDEX IF NOT EXISTS idx_training_progress_course
    ON public.training_progress(course_id);

-- 索引：用户+课程联合查询
CREATE INDEX IF NOT EXISTS idx_training_progress_user_course
    ON public.training_progress(user_id, course_id);

-- ============================================
-- 2. 启用 RLS
-- ============================================
ALTER TABLE public.training_progress ENABLE ROW LEVEL SECURITY;

-- 删除已有策略（幂等）
DROP POLICY IF EXISTS "training_progress_select_policy" ON public.training_progress;
DROP POLICY IF EXISTS "training_progress_insert_policy" ON public.training_progress;
DROP POLICY IF EXISTS "training_progress_update_policy" ON public.training_progress;

-- 查询：用户可查看自己的进度，管理员可查看组织所有成员的进度
CREATE POLICY "training_progress_select_policy"
    ON public.training_progress FOR SELECT
    USING (
        user_id = auth.uid()
        OR organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
              AND role IN ('boss', 'founder')
        )
    );

-- 插入：用户可记录自己的进度
CREATE POLICY "training_progress_insert_policy"
    ON public.training_progress FOR INSERT
    WITH CHECK (
        user_id = auth.uid()
    );

-- 更新：用户可更新自己的进度
CREATE POLICY "training_progress_update_policy"
    ON public.training_progress FOR UPDATE
    USING (
        user_id = auth.uid()
    );

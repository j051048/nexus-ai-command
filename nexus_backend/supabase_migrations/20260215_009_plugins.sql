-- ============================================
-- 插件市场: 数据库迁移
-- Version: 20260215_009
-- Description: installed_plugins 表, RLS 策略
-- ============================================

-- ============================================
-- 1. 创建 installed_plugins 表
-- ============================================
CREATE TABLE IF NOT EXISTS public.installed_plugins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    plugin_id TEXT NOT NULL,
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    installed_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, plugin_id)
);

-- 索引：按组织查询
CREATE INDEX IF NOT EXISTS idx_installed_plugins_org
    ON public.installed_plugins(organization_id);

-- 索引：按插件ID查询
CREATE INDEX IF NOT EXISTS idx_installed_plugins_plugin
    ON public.installed_plugins(plugin_id);

-- ============================================
-- 2. 启用 RLS
-- ============================================
ALTER TABLE public.installed_plugins ENABLE ROW LEVEL SECURITY;

-- 删除已有策略（幂等）
DROP POLICY IF EXISTS "installed_plugins_select_policy" ON public.installed_plugins;
DROP POLICY IF EXISTS "installed_plugins_insert_policy" ON public.installed_plugins;
DROP POLICY IF EXISTS "installed_plugins_update_policy" ON public.installed_plugins;
DROP POLICY IF EXISTS "installed_plugins_delete_policy" ON public.installed_plugins;

-- 查询：组织成员可查看本组织已安装插件
CREATE POLICY "installed_plugins_select_policy"
    ON public.installed_plugins FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM public.profiles
            WHERE id = auth.uid()
        )
    );

-- 插入：仅管理员可安装插件
CREATE POLICY "installed_plugins_insert_policy"
    ON public.installed_plugins FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM public.profiles
            WHERE id = auth.uid()
              AND role IN ('boss', 'admin')
        )
    );

-- 更新：仅管理员可更新配置
CREATE POLICY "installed_plugins_update_policy"
    ON public.installed_plugins FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.profiles
            WHERE id = auth.uid()
              AND role IN ('boss', 'admin')
        )
    );

-- 删除：仅管理员可卸载
CREATE POLICY "installed_plugins_delete_policy"
    ON public.installed_plugins FOR DELETE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.profiles
            WHERE id = auth.uid()
              AND role IN ('boss', 'admin')
        )
    );

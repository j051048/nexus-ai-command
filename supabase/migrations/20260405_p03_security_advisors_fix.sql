-- P0-3: Supabase Security Advisors 修复
-- 修复 RLS Enabled No Policy 的表（添加基础 org 隔离策略）
-- 修复 RLS Policy Always True 的过于宽松策略

-- ============================================================================
-- 1. 为 RLS Enabled 但无 Policy 的表添加基础策略
-- ============================================================================

-- ai_quality_daily: 内部监控表，仅 service_role 可访问
CREATE POLICY ai_quality_daily_service_only ON public.ai_quality_daily
    FOR ALL TO authenticated
    USING (false);

-- api_usage_logs: 用户只能看自己 api_key 的日志
CREATE POLICY api_usage_logs_own ON public.api_usage_logs
    FOR SELECT TO authenticated
    USING (
        api_key_id IN (SELECT id FROM public.api_keys WHERE created_by = auth.uid())
    );

-- contract_events: 用户自己的操作可见
CREATE POLICY contract_events_own ON public.contract_events
    FOR ALL TO authenticated
    USING (user_id = auth.uid());

-- llm_adapter: 管理员配置表，普通用户只读
CREATE POLICY llm_adapter_read ON public.llm_adapter
    FOR SELECT TO authenticated
    USING (true);

-- migration_history: 内部表，不对外暴露
CREATE POLICY migration_history_deny ON public.migration_history
    FOR ALL TO authenticated
    USING (false);

-- oauth_clients: 用 org_id 隔离
CREATE POLICY oauth_clients_org ON public.oauth_clients
    FOR ALL TO authenticated
    USING (
        org_id = (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- user_notification_preferences: 用户只能管理自己的偏好
CREATE POLICY user_notification_preferences_own ON public.user_notification_preferences
    FOR ALL TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- ============================================================================
-- 2. 收紧 RLS Policy Always True 的策略（限定 service_role）
-- ============================================================================

-- oauth_tokens: 改为仅 service_role 可操作（通过限定 role）
DROP POLICY IF EXISTS oauth_tokens_service_key ON public.oauth_tokens;
CREATE POLICY oauth_tokens_service_key ON public.oauth_tokens
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- 用户只能看自己的 token
CREATE POLICY oauth_tokens_own ON public.oauth_tokens
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

-- semantic_cache: 限定 service_role
DROP POLICY IF EXISTS "Service can manage semantic cache" ON public.semantic_cache;
CREATE POLICY semantic_cache_service_only ON public.semantic_cache
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- 用户可读自己的缓存
CREATE POLICY semantic_cache_own_read ON public.semantic_cache
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

-- user_token_usage: 限定 service_role 写，用户可读自己的
DROP POLICY IF EXISTS "Service can manage token usage" ON public.user_token_usage;
CREATE POLICY user_token_usage_service_write ON public.user_token_usage
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY user_token_usage_own_read ON public.user_token_usage
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

-- document_access_groups: 收紧 INSERT 策略
DROP POLICY IF EXISTS dag_insert_policy ON public.document_access_groups;
CREATE POLICY dag_insert_own ON public.document_access_groups
    FOR INSERT TO authenticated
    WITH CHECK (granted_by = auth.uid());

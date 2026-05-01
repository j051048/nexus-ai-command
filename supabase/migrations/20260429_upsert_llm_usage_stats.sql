-- 创建 upsert_llm_usage_stats RPC 函数
-- 被 app/services/llm_quota_service.py:record_usage() 调用
-- 每次 LLM 调用完成后累加用量统计

CREATE OR REPLACE FUNCTION upsert_llm_usage_stats(
  p_tenant_id uuid,
  p_model_code varchar,
  p_user_id uuid,
  p_stat_date date,
  p_input_tokens bigint,
  p_output_tokens bigint,
  p_cost decimal
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  INSERT INTO llm_usage_stats (
    tenant_id, stat_date, model_code, user_id,
    total_calls, total_input_tokens, total_output_tokens, total_cost, success_count
  ) VALUES (
    p_tenant_id, p_stat_date, p_model_code, p_user_id,
    1, p_input_tokens, p_output_tokens, p_cost, 1
  )
  ON CONFLICT (tenant_id, stat_date, model_code, scene_code, agent_code, user_id)
  DO UPDATE SET
    total_calls         = llm_usage_stats.total_calls + 1,
    total_input_tokens  = llm_usage_stats.total_input_tokens + EXCLUDED.total_input_tokens,
    total_output_tokens = llm_usage_stats.total_output_tokens + EXCLUDED.total_output_tokens,
    total_cost          = llm_usage_stats.total_cost + EXCLUDED.total_cost,
    success_count       = llm_usage_stats.success_count + 1;
END;
$$;

-- P2-#9: AI 行为偏好 — 扩展 ai_settings 表支持用户行为偏好
ALTER TABLE ai_settings ADD COLUMN IF NOT EXISTS behavior_preferences JSONB DEFAULT '{}'::jsonb;
COMMENT ON COLUMN ai_settings.behavior_preferences IS '用户AI行为偏好: response_style(concise/detailed), preferred_chart(bar/line/pie/area), auto_expand_trace(bool), language(zh/en)';

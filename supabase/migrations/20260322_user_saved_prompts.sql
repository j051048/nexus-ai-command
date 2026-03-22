-- 用户快捷指令表：存储用户保存的常用 prompt
CREATE TABLE IF NOT EXISTS user_saved_prompts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  tenant_id UUID,
  title TEXT NOT NULL CHECK (char_length(title) <= 100),
  prompt TEXT NOT NULL CHECK (char_length(prompt) <= 2000),
  icon TEXT DEFAULT 'zap',
  sort_order INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_saved_prompts_user ON user_saved_prompts(user_id);

ALTER TABLE user_saved_prompts ENABLE ROW LEVEL SECURITY;

-- RLS: 用户只能管理自己的快捷指令
CREATE POLICY "Users manage own prompts"
  ON user_saved_prompts FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

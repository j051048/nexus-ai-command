-- P3: 聊天图片附件表（独立于 RAG 知识库管线）
-- 用于存储用户在聊天中上传的图片，供 recognize_invoice 等 Vision 工具使用

CREATE TABLE IF NOT EXISTS chat_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    base64_data TEXT NOT NULL,
    size_bytes INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_attachments_user
    ON chat_attachments(user_id, created_at DESC);

-- RLS
ALTER TABLE chat_attachments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own attachments"
    ON chat_attachments FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access on chat_attachments"
    ON chat_attachments FOR ALL
    USING (auth.role() = 'service_role');

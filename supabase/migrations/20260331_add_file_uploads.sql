-- 文件上传表
CREATE TABLE IF NOT EXISTS file_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('contract', 'tender', 'document', 'other')),
    storage_path TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_size INTEGER,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_file_uploads_org_id ON file_uploads(org_id);
CREATE INDEX IF NOT EXISTS idx_file_uploads_file_type ON file_uploads(file_type);

-- RLS 策略
ALTER TABLE file_uploads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "用户只能访问自己组织的文件"
    ON file_uploads FOR ALL
    USING (org_id = current_setting('app.current_org_id', TRUE));

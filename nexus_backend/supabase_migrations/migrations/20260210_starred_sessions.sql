CREATE TABLE IF NOT EXISTS starred_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, session_id)
);

ALTER TABLE starred_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_manage_own_stars" ON starred_sessions
    FOR ALL USING (user_id = auth.uid());

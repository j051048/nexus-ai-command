-- S-2 Fix: OAuth clients DB persistence
-- Provides durable storage for OAuth clients so they survive restarts

CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id TEXT PRIMARY KEY,
    client_secret_hash TEXT NOT NULL,
    client_name TEXT NOT NULL,
    org_id UUID NOT NULL REFERENCES organizations(id),
    redirect_uris JSONB NOT NULL DEFAULT '[]',
    allowed_scopes JSONB NOT NULL DEFAULT '[]',
    grant_types JSONB NOT NULL DEFAULT '["authorization_code"]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oauth_clients_org
    ON oauth_clients(org_id) WHERE is_active = TRUE;

ALTER TABLE oauth_clients ENABLE ROW LEVEL SECURITY;

CREATE POLICY "oauth_clients_org_isolation" ON oauth_clients
    FOR ALL USING (org_id = current_setting('app.current_org_id', true)::uuid);

-- OAuth tokens table (add revoked_at column if table exists, or create it)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'oauth_tokens') THEN
        CREATE TABLE oauth_tokens (
            id BIGSERIAL PRIMARY KEY,
            token_hash TEXT NOT NULL,
            refresh_token_hash TEXT,
            client_id TEXT NOT NULL REFERENCES oauth_clients(client_id),
            user_id UUID NOT NULL,
            scopes JSONB NOT NULL DEFAULT '[]',
            expires_at BIGINT NOT NULL,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE UNIQUE INDEX idx_oauth_tokens_hash ON oauth_tokens(token_hash);
        CREATE INDEX idx_oauth_tokens_refresh ON oauth_tokens(refresh_token_hash);
        CREATE INDEX idx_oauth_tokens_client ON oauth_tokens(client_id);

        ALTER TABLE oauth_tokens ENABLE ROW LEVEL SECURITY;

        CREATE POLICY "oauth_tokens_user_isolation" ON oauth_tokens
            FOR ALL USING (user_id = auth.uid());
    ELSE
        -- Add revoked_at column if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'oauth_tokens' AND column_name = 'revoked_at'
        ) THEN
            ALTER TABLE oauth_tokens ADD COLUMN revoked_at TIMESTAMPTZ;
        END IF;
    END IF;
END $$;

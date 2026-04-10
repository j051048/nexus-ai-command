-- Add white-label branding columns to organizations table
ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS brand jsonb DEFAULT '{}';

-- brand jsonb structure:
-- {
--   "logo_url": "https://...",          -- Organization logo URL
--   "primary_color": "#3b82f6",        -- Primary theme color (hex)
--   "company_name": "My Company",      -- Display name override
--   "tagline": "...",                   -- Tagline/subtitle
--   "login_title": "...",              -- Login page headline
--   "login_subtitle": "...",           -- Login page subtitle
--   "feature_cards": [                 -- Custom feature cards on login
--     {"icon": "sparkles", "title": "...", "desc": "..."}
--   ],
--   "favicon_url": "https://...",      -- Custom favicon
--   "custom_domain": "app.myco.com"   -- Custom domain (future)
-- }

-- Index for fast brand lookup
CREATE INDEX IF NOT EXISTS idx_organizations_brand ON organizations USING gin (brand jsonb_path_ops);

COMMENT ON COLUMN organizations.brand IS 'White-label branding configuration (logo, colors, custom text, domain)';

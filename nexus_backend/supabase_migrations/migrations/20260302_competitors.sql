-- ═══════════════════════════════════════════════════════════
-- 竞品打击库 结构化数据表
-- 支持多租户、产品级对比、维度化打击策略
-- ═══════════════════════════════════════════════════════════

-- 1. 竞品公司表
CREATE TABLE IF NOT EXISTS competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    brand_names TEXT[] DEFAULT '{}',
    industry VARCHAR(100),
    tag VARCHAR(50),
    logo_url VARCHAR(500),
    website VARCHAR(500),
    description TEXT,
    strength_summary TEXT,
    weakness_summary TEXT,
    threat_level VARCHAR(20) DEFAULT 'medium'
        CHECK (threat_level IN ('low', 'medium', 'high', 'critical')),
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, name)
);

CREATE INDEX IF NOT EXISTS idx_competitors_org ON competitors(organization_id);
CREATE INDEX IF NOT EXISTS idx_competitors_active ON competitors(organization_id, is_active);

ALTER TABLE competitors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "competitors_select" ON competitors
    FOR SELECT TO authenticated
    USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "competitors_insert" ON competitors
    FOR INSERT TO authenticated
    WITH CHECK (
        organization_id = public.get_user_org_id(auth.uid())
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.role IN ('founder', 'admin', 'boss')
        )
    );

CREATE POLICY "competitors_update" ON competitors
    FOR UPDATE TO authenticated
    USING (organization_id = public.get_user_org_id(auth.uid()))
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.role IN ('founder', 'admin', 'boss')
        )
    );

CREATE POLICY "competitors_delete" ON competitors
    FOR DELETE TO authenticated
    USING (
        organization_id = public.get_user_org_id(auth.uid())
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.role IN ('founder', 'admin', 'boss')
        )
    );

-- 2. 竞品产品表
CREATE TABLE IF NOT EXISTS competitor_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor_id UUID NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    model VARCHAR(100),
    category VARCHAR(100),
    price_range VARCHAR(100),
    description TEXT,
    specs JSONB DEFAULT '{}',
    our_competing_product VARCHAR(200),
    comparison_notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comp_products_competitor ON competitor_products(competitor_id);

ALTER TABLE competitor_products ENABLE ROW LEVEL SECURITY;

CREATE POLICY "competitor_products_all" ON competitor_products
    FOR ALL TO authenticated
    USING (organization_id = public.get_user_org_id(auth.uid()));

-- 3. 竞品对比维度表
CREATE TABLE IF NOT EXISTS competitor_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor_id UUID NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    dimension VARCHAR(100) NOT NULL,
    competitor_score INT CHECK (competitor_score BETWEEN 1 AND 10),
    our_score INT CHECK (our_score BETWEEN 1 AND 10),
    competitor_detail TEXT,
    our_advantage TEXT,
    counter_strategy TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(competitor_id, dimension)
);

CREATE INDEX IF NOT EXISTS idx_comp_features_competitor ON competitor_features(competitor_id);

ALTER TABLE competitor_features ENABLE ROW LEVEL SECURITY;

CREATE POLICY "competitor_features_all" ON competitor_features
    FOR ALL TO authenticated
    USING (organization_id = public.get_user_org_id(auth.uid()));

-- 4. 竞品关联文档表 (多对多)
CREATE TABLE IF NOT EXISTS competitor_documents (
    competitor_id UUID NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    doc_type VARCHAR(50) DEFAULT 'general',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (competitor_id, document_id)
);

ALTER TABLE competitor_documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "competitor_documents_all" ON competitor_documents
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM competitors c
            WHERE c.id = competitor_id
            AND c.organization_id = public.get_user_org_id(auth.uid())
        )
    );

-- 5. updated_at 触发器
CREATE TRIGGER update_competitors_updated_at
    BEFORE UPDATE ON competitors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_competitor_products_updated_at
    BEFORE UPDATE ON competitor_products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_competitor_features_updated_at
    BEFORE UPDATE ON competitor_features
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

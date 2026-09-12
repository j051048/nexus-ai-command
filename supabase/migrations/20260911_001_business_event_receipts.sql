-- Consumer deduplication for legacy handlers. Stale processing requires reconciliation.
BEGIN;
CREATE TABLE IF NOT EXISTS public.business_event_receipts (
    organization_id uuid NOT NULL REFERENCES public.organizations(id),
    event_id text NOT NULL,
    handler text NOT NULL,
    actor_id uuid NOT NULL,
    payload_hash text NOT NULL,
    status text NOT NULL DEFAULT 'processing'
        CHECK (status IN ('processing', 'completed', 'needs_attention')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, event_id, handler)
);
ALTER TABLE public.business_event_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.business_event_receipts FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.business_event_receipts TO service_role;
CREATE POLICY business_event_receipts_service_only ON public.business_event_receipts
    FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE INDEX IF NOT EXISTS idx_business_event_receipts_attention
    ON public.business_event_receipts (status, created_at)
    WHERE status <> 'completed';

CREATE OR REPLACE FUNCTION public.claim_business_event_receipt(
    p_organization_id uuid, p_event_id text, p_handler text, p_actor_id uuid, p_payload jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $$
DECLARE
    inserted_count integer;
    existing public.business_event_receipts;
    fingerprint text := encode(sha256(convert_to(p_payload::text, 'UTF8')), 'hex');
BEGIN
    IF p_organization_id IS NULL OR p_actor_id IS NULL OR
       COALESCE(p_event_id, '') = '' OR COALESCE(p_handler, '') = '' THEN
        RAISE EXCEPTION 'Business event identity is required';
    END IF;
    INSERT INTO public.business_event_receipts
        (organization_id, event_id, handler, actor_id, payload_hash)
    VALUES (p_organization_id, p_event_id, p_handler, p_actor_id, fingerprint)
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    SELECT * INTO existing FROM public.business_event_receipts
        WHERE organization_id = p_organization_id AND event_id = p_event_id AND handler = p_handler;
    IF existing.payload_hash <> fingerprint OR existing.actor_id <> p_actor_id THEN
        RAISE EXCEPTION 'Business event id reused with a different payload';
    END IF;
    RETURN jsonb_build_object('claimed', inserted_count = 1, 'status', existing.status);
END;
$$;
REVOKE ALL ON FUNCTION public.claim_business_event_receipt(uuid,text,text,uuid,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_business_event_receipt(uuid,text,text,uuid,jsonb) TO service_role;
COMMIT;

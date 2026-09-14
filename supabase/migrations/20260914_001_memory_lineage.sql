-- Derived memory remains unavailable until regenerated with a complete source snapshot.
BEGIN;

ALTER TABLE public.memory_consolidations
  ADD COLUMN IF NOT EXISTS source_fingerprints jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS invalidated_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_memory_consolidations_sources
  ON public.memory_consolidations USING gin (source_memory_ids);

CREATE OR REPLACE FUNCTION public.invalidate_derived_memory()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND
    (to_jsonb(OLD) - ARRAY['access_count', 'last_accessed_at', 'updated_at', 'importance', 'is_consolidated', 'connections'])
    IS NOT DISTINCT FROM
    (to_jsonb(NEW) - ARRAY['access_count', 'last_accessed_at', 'updated_at', 'importance', 'is_consolidated', 'connections'])
  THEN
    RETURN NEW;
  END IF;
  UPDATE public.memory_consolidations
     SET invalidated_at = now()
   WHERE organization_id IS NOT DISTINCT FROM OLD.organization_id
     AND user_id = OLD.user_id
     AND OLD.id::text = ANY(source_memory_ids::text[])
     AND invalidated_at IS NULL;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.invalidate_derived_memory() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS trg_invalidate_derived_memory ON public.conversation_memories;
CREATE TRIGGER trg_invalidate_derived_memory
  AFTER UPDATE OR DELETE ON public.conversation_memories
  FOR EACH ROW EXECUTE FUNCTION public.invalidate_derived_memory();

-- Make legacy sources eligible for regeneration without publishing unverified old insights.
UPDATE public.conversation_memories AS m SET is_consolidated = false
 WHERE m.is_consolidated = true AND EXISTS (
   SELECT 1 FROM public.memory_consolidations AS c
    WHERE c.organization_id IS NOT DISTINCT FROM m.organization_id
      AND c.user_id = m.user_id AND c.source_fingerprints = '{}'::jsonb
      AND m.id::text = ANY(c.source_memory_ids::text[])
 );
COMMIT;

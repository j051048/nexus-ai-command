BEGIN;

CREATE OR REPLACE FUNCTION public.can_read_artifact(p_artifact_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
 SELECT EXISTS (
   SELECT 1 FROM public.artifacts a
   WHERE a.id = p_artifact_id AND auth.uid() IS NOT NULL
     AND a.organization_id = public.get_user_org_id(auth.uid())
     AND EXISTS (SELECT 1 FROM public.organization_members m
       WHERE m.organization_id = a.organization_id AND m.user_id = auth.uid())
     AND NOT EXISTS (
       SELECT 1 FROM public.artifact_versions v,
         LATERAL jsonb_array_elements(COALESCE(v.evidence_snapshot->'records', '[]'::jsonb)) r
       WHERE v.artifact_id = a.id AND NOT EXISTS (
         SELECT 1 FROM public.documents d WHERE d.id::text = r->>'document_id'
           AND d.organization_id = a.organization_id
           AND d.source_version IS NOT DISTINCT FROM r->>'source_version'
           AND COALESCE(d.status, 'ready') IN ('ready', 'completed')
           AND COALESCE(d.review_status, 'pending') NOT IN ('expired', 'rejected')
           AND (d.valid_until IS NULL OR d.valid_until > now())
           AND to_jsonb(d)->>'deleted_at' IS NULL AND to_jsonb(d)->>'revoked_at' IS NULL
           AND (COALESCE(d.visibility, 'organization') IN ('organization', 'public')
             OR (d.visibility = 'private' AND d.owner_id = auth.uid())
             OR (d.visibility = 'department' AND d.department IS NOT NULL AND EXISTS (
               SELECT 1 FROM public.users u WHERE u.id = auth.uid()
                 AND u.organization_id = a.organization_id AND u.department = d.department)))
       )
     )
 )
$$;
REVOKE ALL ON FUNCTION public.can_read_artifact(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.can_read_artifact(uuid) TO authenticated, service_role;

CREATE POLICY artifact_evidence_read_guard ON public.artifacts AS RESTRICTIVE
 FOR SELECT TO authenticated USING (public.can_read_artifact(id));
CREATE POLICY artifact_version_read_guard ON public.artifact_versions AS RESTRICTIVE
 FOR SELECT TO authenticated USING (public.can_read_artifact(artifact_id));
CREATE POLICY artifact_links_read_guard ON public.artifact_evidence_links AS RESTRICTIVE
 FOR SELECT TO authenticated USING (public.can_read_artifact(artifact_id));
CREATE POLICY artifact_review_read_guard ON public.artifact_reviews AS RESTRICTIVE
 FOR SELECT TO authenticated USING (public.can_read_artifact(artifact_id));
CREATE POLICY artifact_feedback_read_guard ON public.artifact_feedback_events AS RESTRICTIVE
 FOR SELECT TO authenticated USING (public.can_read_artifact(artifact_id));

-- Generation may create a draft, never a pre-approved artifact.
CREATE POLICY artifact_draft_insert_guard ON public.artifacts AS RESTRICTIVE
 FOR INSERT TO authenticated WITH CHECK (created_by = auth.uid() AND approval_status = 'pending'
   AND status IN ('queued', 'generating', 'review', 'needs_revision', 'failed'));
CREATE POLICY artifact_version_insert_guard ON public.artifact_versions AS RESTRICTIVE
 FOR INSERT TO authenticated WITH CHECK (created_by = auth.uid() AND EXISTS (
   SELECT 1 FROM public.artifacts a WHERE a.id = artifact_id
     AND a.created_by = auth.uid() AND a.approval_status = 'pending'));
CREATE POLICY artifact_links_insert_guard ON public.artifact_evidence_links AS RESTRICTIVE
 FOR INSERT TO authenticated WITH CHECK (EXISTS (
   SELECT 1 FROM public.artifacts a WHERE a.id = artifact_id
     AND a.created_by = auth.uid() AND a.approval_status = 'pending'));

-- Review RPC is the only authenticated write path for approval. Reviewed
-- content is immutable; revisions create a new artifact and require new review.
REVOKE UPDATE, DELETE ON public.artifacts, public.artifact_versions,
 public.artifact_evidence_links, public.artifact_reviews FROM authenticated, anon;
REVOKE INSERT ON public.artifact_reviews FROM authenticated, anon;

CREATE OR REPLACE FUNCTION public.review_artifact_version(
 p_artifact_id uuid, p_version_id uuid, p_decision text, p_confirmations jsonb,
 p_notes text DEFAULT NULL
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$ DECLARE a public.artifacts%ROWTYPE; v public.artifact_versions%ROWTYPE; BEGIN
 SELECT * INTO a FROM public.artifacts WHERE id = p_artifact_id FOR UPDATE;
 IF NOT FOUND OR NOT public.can_read_artifact(p_artifact_id)
   OR NOT (a.created_by = auth.uid() OR public.can_administer_members(a.organization_id))
 THEN RAISE EXCEPTION 'artifact review forbidden' USING ERRCODE = '42501'; END IF;
 SELECT * INTO v FROM public.artifact_versions
   WHERE id = p_version_id AND artifact_id = a.id AND version_number = a.latest_version;
 IF NOT FOUND THEN RAISE EXCEPTION 'artifact version changed' USING ERRCODE = '40001'; END IF;
 IF p_decision NOT IN ('approved', 'rejected') THEN RAISE EXCEPTION 'invalid review'; END IF;
 IF p_decision = 'approved' AND (
   COALESCE(v.quality_snapshot->>'ready', 'false') <> 'true'
   OR COALESCE(p_confirmations->>'facts', 'false') <> 'true'
   OR COALESCE(p_confirmations->>'promises', 'false') <> 'true'
 ) THEN RAISE EXCEPTION 'quality and human confirmation required' USING ERRCODE = '23514'; END IF;
 INSERT INTO public.artifact_reviews(organization_id, artifact_id, artifact_version_id,
   reviewer_id, decision, notes, confirmations)
 VALUES (a.organization_id, a.id, v.id, auth.uid(), p_decision, p_notes, p_confirmations);
 UPDATE public.artifacts SET approval_status = p_decision,
   status = CASE WHEN p_decision = 'approved' THEN 'approved' ELSE 'needs_revision' END,
   updated_at = now() WHERE id = a.id;
END $$;
REVOKE ALL ON FUNCTION public.review_artifact_version(uuid, uuid, text, jsonb, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.review_artifact_version(uuid, uuid, text, jsonb, text) TO authenticated;

NOTIFY pgrst, 'reload schema';
COMMIT;

-- Compose tenant boundaries with owner/manager permissions instead of OR-ing them.
-- Existing permissive policies remain grants; these guards can only restrict them.
BEGIN;

CREATE OR REPLACE FUNCTION public.can_manage_knowledge_record(p_org_id uuid, p_owner_id uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
    SELECT auth.uid() IS NOT NULL
       AND p_org_id::text = public.current_tenant_id_text()
       AND EXISTS (
           SELECT 1 FROM public.organization_members m
           WHERE m.organization_id = p_org_id AND m.user_id = auth.uid()
             AND (p_owner_id = auth.uid() OR m.role IN ('admin', 'manager', 'boss', 'founder', 'owner'))
       );
$$;
REVOKE ALL ON FUNCTION public.can_manage_knowledge_record(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.can_manage_knowledge_record(uuid, uuid) TO authenticated, service_role;

ALTER TABLE public.knowledge_graph_triples ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS quality_knowledge_graph_triples_tenant ON public.knowledge_graph_triples;
CREATE POLICY quality_knowledge_graph_triples_tenant ON public.knowledge_graph_triples
AS RESTRICTIVE FOR ALL TO authenticated
USING (
    organization_id::text = public.current_tenant_id_text()
    AND EXISTS (SELECT 1 FROM public.organization_members m
                WHERE m.organization_id = knowledge_graph_triples.organization_id AND m.user_id = auth.uid())
)
WITH CHECK (
    organization_id::text = public.current_tenant_id_text()
    AND EXISTS (SELECT 1 FROM public.organization_members m
                WHERE m.organization_id = knowledge_graph_triples.organization_id AND m.user_id = auth.uid())
);
DROP POLICY IF EXISTS quality_knowledge_graph_triples_read ON public.knowledge_graph_triples;
CREATE POLICY quality_knowledge_graph_triples_read ON public.knowledge_graph_triples
AS RESTRICTIVE FOR SELECT TO authenticated
USING (user_id = auth.uid() OR visibility IN ('team', 'organization'));
DROP POLICY IF EXISTS quality_knowledge_graph_triples_insert ON public.knowledge_graph_triples;
CREATE POLICY quality_knowledge_graph_triples_insert ON public.knowledge_graph_triples
AS RESTRICTIVE FOR INSERT TO authenticated
WITH CHECK (public.can_manage_knowledge_record(organization_id, user_id));
DROP POLICY IF EXISTS quality_knowledge_graph_triples_update ON public.knowledge_graph_triples;
CREATE POLICY quality_knowledge_graph_triples_update ON public.knowledge_graph_triples
AS RESTRICTIVE FOR UPDATE TO authenticated
USING (public.can_manage_knowledge_record(organization_id, user_id))
WITH CHECK (public.can_manage_knowledge_record(organization_id, user_id));
DROP POLICY IF EXISTS quality_knowledge_graph_triples_delete ON public.knowledge_graph_triples;
CREATE POLICY quality_knowledge_graph_triples_delete ON public.knowledge_graph_triples
AS RESTRICTIVE FOR DELETE TO authenticated
USING (public.can_manage_knowledge_record(organization_id, user_id));

ALTER TABLE public.conversation_memories ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS quality_conversation_memories_tenant ON public.conversation_memories;
CREATE POLICY quality_conversation_memories_tenant ON public.conversation_memories
AS RESTRICTIVE FOR ALL TO authenticated
USING (
    organization_id::text = public.current_tenant_id_text()
    AND EXISTS (SELECT 1 FROM public.organization_members m
                WHERE m.organization_id = conversation_memories.organization_id AND m.user_id = auth.uid())
)
WITH CHECK (
    organization_id::text = public.current_tenant_id_text()
    AND EXISTS (SELECT 1 FROM public.organization_members m
                WHERE m.organization_id = conversation_memories.organization_id AND m.user_id = auth.uid())
);
DROP POLICY IF EXISTS quality_conversation_memories_read ON public.conversation_memories;
CREATE POLICY quality_conversation_memories_read ON public.conversation_memories
AS RESTRICTIVE FOR SELECT TO authenticated
USING (user_id = auth.uid() OR visibility IN ('team', 'organization'));
DROP POLICY IF EXISTS quality_conversation_memories_insert ON public.conversation_memories;
CREATE POLICY quality_conversation_memories_insert ON public.conversation_memories
AS RESTRICTIVE FOR INSERT TO authenticated
WITH CHECK (public.can_manage_knowledge_record(organization_id, user_id));
DROP POLICY IF EXISTS quality_conversation_memories_update ON public.conversation_memories;
CREATE POLICY quality_conversation_memories_update ON public.conversation_memories
AS RESTRICTIVE FOR UPDATE TO authenticated
USING (public.can_manage_knowledge_record(organization_id, user_id))
WITH CHECK (public.can_manage_knowledge_record(organization_id, user_id));
DROP POLICY IF EXISTS quality_conversation_memories_delete ON public.conversation_memories;
CREATE POLICY quality_conversation_memories_delete ON public.conversation_memories
AS RESTRICTIVE FOR DELETE TO authenticated
USING (public.can_manage_knowledge_record(organization_id, user_id));

COMMIT;

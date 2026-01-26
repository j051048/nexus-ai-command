-- P0 Audit Fix: Enable Row Level Security (RLS) for private documents
-- Ensuring data isolation between different users/roles.
ALTER TABLE public.document_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
-- 1. Document Embeddings Policies
CREATE POLICY "Public Document Embeddings Access" ON public.document_embeddings FOR
SELECT USING (true);
-- Default to public for now if common, but let's restrict if possible.
-- Restricting embeddings access to users who can see the parent document is better
DROP POLICY IF EXISTS "Public Document Embeddings Access" ON public.document_embeddings;
CREATE POLICY "Access Embeddings if can access Document" ON public.document_embeddings FOR ALL USING (
    EXISTS (
        SELECT 1
        FROM public.documents
        WHERE public.documents.id = public.document_embeddings.document_id
    )
);
-- 2. Documents Policies
-- Assuming a simple model where document owner is stored 
-- or 'founder' can see everything.
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES public.users(id);
CREATE POLICY "Users can see own documents" ON public.documents FOR
SELECT USING (
        auth.uid() = owner_id
        OR EXISTS (
            SELECT 1
            FROM public.users
            WHERE id = auth.uid()
                AND role = 'founder'
        )
    );
CREATE POLICY "Users can insert own documents" ON public.documents FOR
INSERT WITH CHECK (auth.uid() = owner_id);
-- Update existing documents to belong to the first founder found if any
DO $$
DECLARE first_founder_id uuid;
BEGIN
SELECT id INTO first_founder_id
FROM public.users
WHERE role = 'founder'
LIMIT 1;
IF first_founder_id IS NOT NULL THEN
UPDATE public.documents
SET owner_id = first_founder_id
WHERE owner_id IS NULL;
END IF;
END $$;
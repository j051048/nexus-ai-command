-- Fix for BUG-004: Update match_documents to support metadata filtering
-- This allows the Hybrid Search P2 Optimization to actually work on the DB side.
drop function if exists match_documents;
create or replace function match_documents (
        query_embedding vector(1536),
        match_threshold float,
        match_count int,
        filter jsonb default '{}'
    ) returns table (
        id bigint,
        content text,
        metadata jsonb,
        similarity float
    ) language plpgsql as $$ begin return query
select document_embeddings.id,
    document_embeddings.content,
    document_embeddings.metadata,
    1 - (
        document_embeddings.embedding <=> query_embedding
    ) as similarity
from document_embeddings
where 1 - (
        document_embeddings.embedding <=> query_embedding
    ) > match_threshold
    and document_embeddings.metadata @> filter
order by document_embeddings.embedding <=> query_embedding
limit match_count;
end;
$$;
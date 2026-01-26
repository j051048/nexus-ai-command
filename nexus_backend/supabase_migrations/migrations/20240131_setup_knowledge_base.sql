-- Enable the pgvector extension to work with embedding vectors
create extension if not exists vector;
-- Create a table to store your documents
create table if not exists document_embeddings (
    id bigserial primary key,
    content text,
    metadata jsonb,
    embedding vector(1536)
);
-- Index for faster search (IVFFlat)
-- Note: It's often recommended to create this after some data is inserted, but defining it here for completeness
-- create index on document_embeddings using ivfflat (embedding vector_cosine_ops) with (lists = 100);
-- Create a function to search for documents
create or replace function match_documents (
        query_embedding vector(1536),
        match_threshold float,
        match_count int
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
order by document_embeddings.embedding <=> query_embedding
limit match_count;
end;
$$;
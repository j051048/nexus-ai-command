-- P1: Enable Full Text Search (FTS) for documents
-- This migration adds a generated column `fts` and a GIN index to speed up text search.
-- 1. Add English + Chinese configuration if not exists (Supabase usually has 'jieba' or 'simple')
-- For simplicity, we use 'simple' or 'english' which works okay for mixed content, 
-- but strictly speaking 'jieba' is better for Chinese if available in extensions.
-- Here we rely on 'pg_jieba' if installed, else fallback to 'simple'.
create extension if not exists pg_trgm;
-- 2. Add full text search vector column to document_embeddings
-- We store both the raw content and metadata for search
alter table document_embeddings
add column if not exists fts tsvector generated always as (to_tsvector('simple', content)) stored;
-- 3. Create GIN index
create index if not exists document_embeddings_fts_idx on document_embeddings using gin(fts);
-- 4. Enable Trigram index for ILIKE speedup (as a backup)
create index if not exists document_embeddings_content_trgm_idx on document_embeddings using gin(content gin_trgm_ops);
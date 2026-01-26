-- Create documents table for Smart Document Management (Module 2)
create table if not exists documents (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    doc_type text,
    -- contract, bid, quote, etc.
    version int default 1,
    parent_id uuid references documents(id),
    extracted_data jsonb default '{}',
    -- AI extracted metadata: amount, client, dates
    owner_id uuid references users(id),
    -- For RLS
    department_id text,
    created_at timestamptz default now()
);
-- Row Level Security (RLS) Policies
-- For MVP, we will keep it simple but structure is here
-- alter table documents enable row level security;
-- create policy "Users can see own docs" on documents for select using (auth.uid() = owner_id);
-- Update document_embeddings to link to documents table
-- This allows hybrid search (Vector + Metadata)
alter table document_embeddings
add column document_id uuid references documents(id);
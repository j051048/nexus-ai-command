-- P1 Fix #20: Document content hash for deduplication
-- Allows detecting duplicate uploads based on file content fingerprint.

-- Add content_hash column to documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash text;

-- Create index for fast dedup lookups (per user)
CREATE INDEX IF NOT EXISTS idx_documents_content_hash_owner 
    ON documents(content_hash, owner_id) 
    WHERE content_hash IS NOT NULL;

-- Optional: backfill existing documents (content_hash will be NULL for old docs,
-- which is fine — dedup only applies to new uploads)
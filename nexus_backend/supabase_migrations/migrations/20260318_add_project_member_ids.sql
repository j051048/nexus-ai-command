-- Add member_ids column to projects table for team member tracking
ALTER TABLE projects ADD COLUMN IF NOT EXISTS member_ids uuid[] DEFAULT '{}';

-- Add comment
COMMENT ON COLUMN projects.member_ids IS 'Array of user IDs who are participants in this project';

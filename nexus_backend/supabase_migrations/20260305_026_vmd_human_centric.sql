-- VMD Task Center: Human-centric redesign
-- Adds human work-tracking columns to vmd_sub_task table
-- All columns have defaults so existing data is unaffected

DO $$
BEGIN
  -- Human progress percentage (0-100), manually set by assignee
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name = 'vmd_sub_task' AND column_name = 'progress') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN progress smallint DEFAULT 0
      CHECK (progress >= 0 AND progress <= 100);
  END IF;

  -- Human notes / deliverable content (authored by human, not AI)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name = 'vmd_sub_task' AND column_name = 'human_notes') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN human_notes text;
  END IF;

  -- Assignee user ID
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name = 'vmd_sub_task' AND column_name = 'assignee_id') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN assignee_id uuid;
  END IF;

  -- Assignee display name (denormalized for convenience)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name = 'vmd_sub_task' AND column_name = 'assignee_name') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN assignee_name varchar(100);
  END IF;

  -- Weight for weighted-average progress calculation (1-10)
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name = 'vmd_sub_task' AND column_name = 'weight') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN weight smallint DEFAULT 1
      CHECK (weight >= 1 AND weight <= 10);
  END IF;

  -- Planned start date
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name = 'vmd_sub_task' AND column_name = 'start_date') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN start_date date;
  END IF;

  -- Planned due date
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
    WHERE table_name = 'vmd_sub_task' AND column_name = 'due_date') THEN
    ALTER TABLE vmd_sub_task ADD COLUMN due_date date;
  END IF;
END $$;

-- Indexes for new columns
CREATE INDEX IF NOT EXISTS idx_vmd_sub_task_assignee
  ON vmd_sub_task(assignee_id) WHERE assignee_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_vmd_sub_task_progress
  ON vmd_sub_task(main_task_id, progress);

-- Column comments
COMMENT ON COLUMN vmd_sub_task.progress IS 'Human-set progress 0-100%';
COMMENT ON COLUMN vmd_sub_task.human_notes IS 'Human-authored notes and deliverables';
COMMENT ON COLUMN vmd_sub_task.weight IS 'Weight for weighted-average progress (1-10)';

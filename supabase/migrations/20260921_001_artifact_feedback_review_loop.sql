-- Artifact feedback review loop.
--
-- Closes three gaps in the edit-diff learning pipeline:
--   1. ``artifact_feedback_events`` never had a ``change_type`` column even
--      though ``record_learning_candidate`` writes one, so every learning
--      candidate insert failed and was silently downgraded to ``recorded``.
--   2. ``rating`` was NOT NULL while the review queue must accept an
--      un-rated edit (a human edited the draft without scoring it).
--   3. Approval had no auditable writer: only the pipeline could set
--      ``learning_status``, and it can only ever set the open states.
--
-- Additive only, no data backfill, safe to replay.

ALTER TABLE public.artifact_feedback_events
    ADD COLUMN IF NOT EXISTS change_type text
        CHECK (
            change_type IS NULL
            OR change_type IN ('accepted', 'edited', 'rejected', 'won', 'lost', 'other')
        ),
    ADD COLUMN IF NOT EXISTS reviewed_by uuid,
    ADD COLUMN IF NOT EXISTS reviewed_at timestamptz,
    ADD COLUMN IF NOT EXISTS review_note text;

-- An un-rated human edit is still a learning signal.
ALTER TABLE public.artifact_feedback_events
    ALTER COLUMN rating DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_artifact_feedback_review_queue
    ON public.artifact_feedback_events
        (organization_id, learning_status, created_at DESC)
    WHERE learning_status IN ('recorded', 'review_candidate');

COMMENT ON COLUMN public.artifact_feedback_events.learning_status IS
    'recorded | review_candidate (pipeline, open) -> approved | rejected (human reviewer only)';

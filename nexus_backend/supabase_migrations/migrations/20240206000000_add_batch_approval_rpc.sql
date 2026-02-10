-- P1 Fix #15: Atomic batch approval via database transaction
-- Prevents partial approval states when processing multiple requests.
-- The entire batch succeeds or fails as one unit.

CREATE OR REPLACE FUNCTION batch_update_approvals(
    p_request_ids uuid[],
    p_new_status text,
    p_approved_by uuid,
    p_comment text DEFAULT ''
) RETURNS jsonb AS $$
DECLARE
    v_updated_count integer := 0;
    v_skipped_count integer := 0;
    v_request_id uuid;
    v_result jsonb;
    v_updated_ids uuid[] := '{}';
    v_skipped_ids uuid[] := '{}';
BEGIN
    -- Validate inputs
    IF p_new_status NOT IN ('approved', 'rejected') THEN
        RAISE EXCEPTION 'Invalid status: %. Must be approved or rejected.', p_new_status;
    END IF;

    -- Process all requests within this single transaction
    FOREACH v_request_id IN ARRAY p_request_ids
    LOOP
        -- Only update if still pending (idempotency check)
        UPDATE approval_requests
        SET 
            status = p_new_status,
            approved_by = p_approved_by,
            approved_at = now(),
            approval_comment = COALESCE(NULLIF(p_comment, ''), 
                CASE p_new_status WHEN 'approved' THEN '已批准' ELSE '已驳回' END)
        WHERE id = v_request_id 
          AND status = 'pending';

        IF FOUND THEN
            v_updated_count := v_updated_count + 1;
            v_updated_ids := array_append(v_updated_ids, v_request_id);
        ELSE
            v_skipped_count := v_skipped_count + 1;
            v_skipped_ids := array_append(v_skipped_ids, v_request_id);
        END IF;
    END LOOP;

    -- Build result
    v_result := jsonb_build_object(
        'updated_count', v_updated_count,
        'skipped_count', v_skipped_count,
        'updated_ids', to_jsonb(v_updated_ids),
        'skipped_ids', to_jsonb(v_skipped_ids)
    );

    -- Insert audit log for the batch operation
    INSERT INTO audit_logs (action, actor_user_id, target_table, details_json)
    VALUES (
        'batch_' || p_new_status,
        p_approved_by,
        'approval_requests',
        jsonb_build_object(
            'updated_count', v_updated_count,
            'skipped_count', v_skipped_count,
            'request_ids', to_jsonb(p_request_ids),
            'comment', p_comment
        )
    );

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;
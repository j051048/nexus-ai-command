-- Atomic inventory mutation and ledger write.
-- Prevents lost updates and partial writes under concurrent warehouse actions.

CREATE OR REPLACE FUNCTION public.adjust_inventory_atomic(
    p_org_id UUID,
    p_item_id UUID,
    p_delta INTEGER,
    p_operator_id UUID,
    p_receiver_id UUID DEFAULT NULL,
    p_reason TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'::JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_current INTEGER;
    v_new INTEGER;
    v_transaction public.inventory_transactions%ROWTYPE;
BEGIN
    IF p_delta = 0 THEN
        RAISE EXCEPTION 'inventory delta must not be zero' USING ERRCODE = '22023';
    END IF;

    SELECT quantity
      INTO v_current
      FROM public.inventory
     WHERE id = p_item_id
       AND organization_id = p_org_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'inventory item not found' USING ERRCODE = 'P0002';
    END IF;

    v_new := v_current + p_delta;
    IF v_new < 0 THEN
        RAISE EXCEPTION 'insufficient inventory' USING ERRCODE = '22003';
    END IF;

    UPDATE public.inventory
       SET quantity = v_new
     WHERE id = p_item_id
       AND organization_id = p_org_id;

    INSERT INTO public.inventory_transactions (
        organization_id, item_id, transaction_type, quantity,
        operator_id, receiver_id, reason, metadata
    ) VALUES (
        p_org_id, p_item_id,
        CASE WHEN p_delta > 0 THEN 'in' ELSE 'out' END,
        ABS(p_delta), p_operator_id, p_receiver_id, p_reason,
        COALESCE(p_metadata, '{}'::JSONB)
    )
    RETURNING * INTO v_transaction;

    RETURN jsonb_build_object(
        'transaction', to_jsonb(v_transaction),
        'previous_quantity', v_current,
        'new_quantity', v_new
    );
END;
$$;

REVOKE ALL ON FUNCTION public.adjust_inventory_atomic(UUID, UUID, INTEGER, UUID, UUID, TEXT, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.adjust_inventory_atomic(UUID, UUID, INTEGER, UUID, UUID, TEXT, JSONB) TO authenticated;
GRANT EXECUTE ON FUNCTION public.adjust_inventory_atomic(UUID, UUID, INTEGER, UUID, UUID, TEXT, JSONB) TO service_role;

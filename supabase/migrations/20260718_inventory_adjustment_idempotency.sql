-- Durable idempotency for inventory mutations.
--
-- HTTP response caching and the in-process Agent cache are useful fast paths,
-- but neither survives every retry or process restart. The ledger therefore
-- owns the final replay guarantee together with the inventory row lock.

ALTER TABLE public.inventory_transactions
  ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_transactions_org_idempotency
  ON public.inventory_transactions (organization_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL;

DROP FUNCTION IF EXISTS public.adjust_inventory_atomic(
  UUID, UUID, INTEGER, UUID, UUID, TEXT, JSONB
);

CREATE OR REPLACE FUNCTION public.adjust_inventory_atomic(
    p_org_id UUID,
    p_item_id UUID,
    p_delta INTEGER,
    p_operator_id UUID,
    p_receiver_id UUID DEFAULT NULL,
    p_reason TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'::JSONB,
    p_idempotency_key TEXT DEFAULT NULL
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
    v_expected_type TEXT;
BEGIN
    IF p_delta = 0 THEN
        RAISE EXCEPTION 'inventory delta must not be zero' USING ERRCODE = '22023';
    END IF;
    IF p_idempotency_key IS NOT NULL
       AND (length(btrim(p_idempotency_key)) < 1 OR length(p_idempotency_key) > 128) THEN
        RAISE EXCEPTION 'invalid inventory idempotency key' USING ERRCODE = '22023';
    END IF;

    v_expected_type := CASE WHEN p_delta > 0 THEN 'in' ELSE 'out' END;

    IF p_idempotency_key IS NOT NULL THEN
        -- Serialize identical keys even when a malformed retry changes the
        -- item id. This turns a concurrent unique-index race into a stable
        -- replay or payload-conflict result.
        PERFORM pg_advisory_xact_lock(
            hashtextextended(
                'inventory:' || p_org_id::TEXT || ':' || p_idempotency_key,
                0
            )
        );
    END IF;

    -- Serializing on the inventory row makes the replay check race-safe. A
    -- concurrent first attempt must commit before a retry can inspect its
    -- ledger row.
    SELECT quantity
      INTO v_current
      FROM public.inventory
     WHERE id = p_item_id
       AND organization_id = p_org_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'inventory item not found' USING ERRCODE = 'P0002';
    END IF;

    IF p_idempotency_key IS NOT NULL THEN
        SELECT *
          INTO v_transaction
          FROM public.inventory_transactions
         WHERE organization_id = p_org_id
           AND idempotency_key = p_idempotency_key;

        IF FOUND THEN
            IF v_transaction.item_id IS DISTINCT FROM p_item_id
               OR v_transaction.transaction_type IS DISTINCT FROM v_expected_type
               OR v_transaction.quantity IS DISTINCT FROM ABS(p_delta)
               OR v_transaction.operator_id IS DISTINCT FROM p_operator_id
               OR v_transaction.receiver_id IS DISTINCT FROM p_receiver_id
               OR v_transaction.reason IS DISTINCT FROM p_reason
               OR coalesce(v_transaction.metadata, '{}'::JSONB)
                  IS DISTINCT FROM coalesce(p_metadata, '{}'::JSONB) THEN
                RAISE EXCEPTION 'inventory idempotency key reused with different payload'
                  USING ERRCODE = '22023';
            END IF;
            RETURN jsonb_build_object(
                'transaction', to_jsonb(v_transaction),
                'previous_quantity', v_current,
                'new_quantity', v_current,
                'replayed', TRUE
            );
        END IF;
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
        operator_id, receiver_id, reason, metadata, idempotency_key
    ) VALUES (
        p_org_id, p_item_id, v_expected_type,
        ABS(p_delta), p_operator_id, p_receiver_id, p_reason,
        COALESCE(p_metadata, '{}'::JSONB), p_idempotency_key
    )
    RETURNING * INTO v_transaction;

    RETURN jsonb_build_object(
        'transaction', to_jsonb(v_transaction),
        'previous_quantity', v_current,
        'new_quantity', v_new,
        'replayed', FALSE
    );
END;
$$;

REVOKE ALL ON FUNCTION public.adjust_inventory_atomic(
  UUID, UUID, INTEGER, UUID, UUID, TEXT, JSONB, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.adjust_inventory_atomic(
  UUID, UUID, INTEGER, UUID, UUID, TEXT, JSONB, TEXT
) TO authenticated;
GRANT EXECUTE ON FUNCTION public.adjust_inventory_atomic(
  UUID, UUID, INTEGER, UUID, UUID, TEXT, JSONB, TEXT
) TO service_role;

COMMENT ON FUNCTION public.adjust_inventory_atomic(
  UUID, UUID, INTEGER, UUID, UUID, TEXT, JSONB, TEXT
) IS 'Atomically adjusts stock and writes its ledger; p_idempotency_key makes retries safe.';

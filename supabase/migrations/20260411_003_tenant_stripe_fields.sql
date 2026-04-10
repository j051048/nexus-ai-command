-- 20260411_003: Add Stripe fields to organizations table
-- Referenced by: payment_gateway.py (.update stripe_customer_id, tier, payment_status)

-- Add stripe_customer_id if not exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'organizations' AND column_name = 'stripe_customer_id'
  ) THEN
    ALTER TABLE organizations ADD COLUMN stripe_customer_id TEXT;
  END IF;
END $$;

-- Add tier if not exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'organizations' AND column_name = 'tier'
  ) THEN
    ALTER TABLE organizations ADD COLUMN tier TEXT NOT NULL DEFAULT 'free';
  END IF;
END $$;

-- Add payment_status if not exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'organizations' AND column_name = 'payment_status'
  ) THEN
    ALTER TABLE organizations ADD COLUMN payment_status TEXT;
  END IF;
END $$;

-- Index for Stripe customer lookups
CREATE INDEX IF NOT EXISTS idx_orgs_stripe_customer ON organizations (stripe_customer_id)
  WHERE stripe_customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orgs_tier ON organizations (tier);

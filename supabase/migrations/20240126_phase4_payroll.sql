-- Phase 4: Algorithmic Payroll & Realtime Notifications
-- 1. Ensure User Wallet Table exists
CREATE TABLE IF NOT EXISTS user_wallets (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id),
    balance NUMERIC DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
-- 2. Ensure Sales Orders Table exists (for triggers)
CREATE TABLE IF NOT EXISTS sales_orders (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    customer_name TEXT,
    amount NUMERIC,
    status TEXT DEFAULT 'pending',
    -- pending, closed, paid
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
-- 3. Trigger Function: Calculate Bonus
CREATE OR REPLACE FUNCTION calculate_instant_bonus() RETURNS TRIGGER AS $$
DECLARE bonus_amount NUMERIC;
BEGIN -- Only trigger for high value deals (> 500,000) that are closed
IF NEW.amount > 500000
AND NEW.status = 'closed' THEN -- Rule: 0.5% commission
bonus_amount := NEW.amount * 0.005;
-- A. Update Wallet
INSERT INTO user_wallets (user_id, balance)
VALUES (NEW.user_id, bonus_amount) ON CONFLICT (user_id) DO
UPDATE
SET balance = user_wallets.balance + excluded.balance,
    updated_at = NOW();
-- B. Send Notification (Frontend Listener)
INSERT INTO notifications (user_id, title, content, type)
VALUES (
        NEW.user_id,
        '💰 即时奖金到账',
        '恭喜！您的一笔大额回款触发了算法激励，奖金 ¥' || bonus_amount || ' 已入账。',
        'bonus'
    );
END IF;
RETURN NEW;
END;
$$ LANGUAGE plpgsql;
-- 4. Create Trigger
DROP TRIGGER IF EXISTS trigger_sales_bonus ON sales_orders;
CREATE TRIGGER trigger_sales_bonus
AFTER
INSERT
    OR
UPDATE ON sales_orders FOR EACH ROW EXECUTE FUNCTION calculate_instant_bonus();
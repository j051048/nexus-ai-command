-- Add columns to users to match profile needs
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS avatar text;
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS score integer DEFAULT 87;
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS rank integer DEFAULT 3;
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS total_bonus numeric(10, 2) DEFAULT 4850;
-- Create RPC for role fetching
CREATE OR REPLACE FUNCTION public.get_user_role(_user_id uuid) RETURNS text AS $$
DECLARE _role public.user_role;
BEGIN
SELECT role INTO _role
FROM public.users
WHERE id = _user_id;
IF _role = 'founder' THEN RETURN 'boss';
ELSIF _role = 'sales' THEN RETURN 'employee';
ELSE RETURN 'employee';
END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
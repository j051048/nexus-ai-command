-- MASTER SETUP SCRIPT for Project Nexus
-- Run this ENTIRE script in Supabase SQL Editor to fix all "Table not found" errors.
-- 1. Create Tables (Idempotent - will skip if exists)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
DO $$ BEGIN CREATE TYPE user_role AS ENUM ('founder', 'sales', 'employee');
EXCEPTION
WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN CREATE TYPE lead_status AS ENUM ('new', 'contacted', 'qualified', 'lost', 'won');
EXCEPTION
WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN CREATE TYPE incentive_type AS ENUM ('bonus', 'badge', 'rank');
EXCEPTION
WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN CREATE TYPE approval_type AS ENUM ('purchase', 'travel', 'event', 'expense');
EXCEPTION
WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected');
EXCEPTION
WHEN duplicate_object THEN null;
END $$;
DO $$ BEGIN CREATE TYPE ai_decision_type AS ENUM ('auto', 'manual');
EXCEPTION
WHEN duplicate_object THEN null;
END $$;
CREATE TABLE IF NOT EXISTS public.users (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name text NOT NULL,
    role user_role NOT NULL DEFAULT 'sales',
    department text,
    avatar text,
    score integer DEFAULT 87,
    rank integer DEFAULT 3,
    total_bonus numeric(10, 2) DEFAULT 4850,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
-- 2. Create the Trigger to auto-sync Users from Auth
CREATE OR REPLACE FUNCTION public.handle_new_user() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE _role public.user_role;
_raw_role text;
_department text;
BEGIN _raw_role := new.raw_user_meta_data->>'role';
IF _raw_role = 'boss' THEN _role := 'founder';
_department := 'Management';
ELSIF _raw_role = 'employee' THEN _role := 'sales';
_department := 'Sales Dept';
ELSE _role := 'sales';
_department := 'Sales Dept';
END IF;
INSERT INTO public.users (
        id,
        name,
        role,
        department,
        created_at,
        updated_at
    )
VALUES (
        new.id,
        COALESCE(new.raw_user_meta_data->>'name', 'New User'),
        _role,
        _department,
        now(),
        now()
    ) ON CONFLICT (id) DO
UPDATE
SET role = EXCLUDED.role,
    department = EXCLUDED.department;
RETURN new;
END;
$$;
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
AFTER
INSERT ON auth.users FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
-- 3. Create Helper RPC
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
-- 4. Enable RLS
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users see own data" ON public.users;
CREATE POLICY "Users see own data" ON public.users FOR
SELECT USING (true);
-- Allow reading public profiles for now to fix search
-- 5. Backfill existing data (Fix your current account)
-- This attempts to insert your current auth user into public.users if missing
INSERT INTO public.users (id, name, role, department)
SELECT id,
    COALESCE(raw_user_meta_data->>'name', email),
    CASE
        WHEN raw_user_meta_data->>'role' = 'boss' THEN 'founder'::user_role
        ELSE 'sales'::user_role
    END,
    CASE
        WHEN raw_user_meta_data->>'role' = 'boss' THEN 'Management'
        ELSE 'Sales Dept'
    END
FROM auth.users ON CONFLICT (id) DO
UPDATE
SET department = EXCLUDED.department,
    role = EXCLUDED.role;
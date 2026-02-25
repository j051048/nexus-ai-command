-- Create enum for user roles
CREATE TYPE public.app_role AS ENUM ('boss', 'employee');

-- Create profiles table for user information
CREATE TABLE public.profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  name TEXT NOT NULL,
  avatar TEXT DEFAULT '',
  department TEXT DEFAULT '销售部',
  score INTEGER DEFAULT 0,
  rank INTEGER DEFAULT 1,
  total_bonus NUMERIC DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- Create user_roles table (separate from profiles for security)
CREATE TABLE public.user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  role app_role NOT NULL DEFAULT 'employee',
  UNIQUE (user_id, role)
);

-- Create badges table
CREATE TABLE public.badges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  name TEXT NOT NULL,
  icon TEXT NOT NULL,
  description TEXT,
  tier TEXT CHECK (tier IN ('bronze', 'silver', 'gold')) DEFAULT 'bronze',
  unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create sales_metrics table for charts
CREATE TABLE public.sales_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  leads_count INTEGER DEFAULT 0,
  conversions INTEGER DEFAULT 0,
  win_rate NUMERIC DEFAULT 0,
  revenue NUMERIC DEFAULT 0,
  calls_made INTEGER DEFAULT 0,
  score INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create team_performance view for aggregated data
CREATE TABLE public.team_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  week_start DATE NOT NULL,
  total_leads INTEGER DEFAULT 0,
  total_conversions INTEGER DEFAULT 0,
  avg_win_rate NUMERIC DEFAULT 0,
  total_revenue NUMERIC DEFAULT 0,
  top_performer_id UUID REFERENCES auth.users(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.badges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sales_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.team_performance ENABLE ROW LEVEL SECURITY;

-- Security definer function to check roles (prevents RLS recursion)
CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role app_role)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = _user_id AND role = _role
  )
$$;

-- Function to get user role
CREATE OR REPLACE FUNCTION public.get_user_role(_user_id UUID)
RETURNS app_role
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT role FROM public.user_roles WHERE user_id = _user_id LIMIT 1
$$;

-- Profiles policies
CREATE POLICY "Users can view all profiles" ON public.profiles
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "Users can update own profile" ON public.profiles
  FOR UPDATE TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own profile" ON public.profiles
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

-- User roles policies  
CREATE POLICY "Users can view own role" ON public.user_roles
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "Boss can view all roles" ON public.user_roles
  FOR SELECT TO authenticated USING (public.has_role(auth.uid(), 'boss'));

-- Badges policies
CREATE POLICY "Users can view own badges" ON public.badges
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "Boss can view all badges" ON public.badges
  FOR SELECT TO authenticated USING (public.has_role(auth.uid(), 'boss'));

-- Sales metrics policies
CREATE POLICY "Users can view own metrics" ON public.sales_metrics
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "Boss can view all metrics" ON public.sales_metrics
  FOR SELECT TO authenticated USING (public.has_role(auth.uid(), 'boss'));

CREATE POLICY "Users can insert own metrics" ON public.sales_metrics
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

-- Team performance policies (boss only for full view)
CREATE POLICY "Boss can view team performance" ON public.team_performance
  FOR SELECT TO authenticated USING (public.has_role(auth.uid(), 'boss'));

CREATE POLICY "Employees can view team performance" ON public.team_performance
  FOR SELECT TO authenticated USING (true);

-- Trigger to auto-create profile and role on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (user_id, name)
  VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'name', NEW.email));
  
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, COALESCE((NEW.raw_user_meta_data->>'role')::app_role, 'employee'));
  
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_profiles_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
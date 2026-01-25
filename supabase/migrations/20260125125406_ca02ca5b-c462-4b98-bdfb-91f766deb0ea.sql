-- Add unique constraint for upsert functionality
ALTER TABLE public.sales_metrics ADD CONSTRAINT sales_metrics_user_date_unique UNIQUE (user_id, date);
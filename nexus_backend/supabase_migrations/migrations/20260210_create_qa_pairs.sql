-- Create qa_pairs table for manual Q&A annotation
CREATE TABLE IF NOT EXISTS public.qa_pairs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  category TEXT,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- Create index for faster question matching
CREATE INDEX IF NOT EXISTS idx_qa_pairs_question ON public.qa_pairs USING gin (to_tsvector('simple', question));
CREATE INDEX IF NOT EXISTS idx_qa_pairs_user_id ON public.qa_pairs (user_id);
CREATE INDEX IF NOT EXISTS idx_qa_pairs_category ON public.qa_pairs (category);

-- Enable RLS
ALTER TABLE public.qa_pairs ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their own qa_pairs"
  ON public.qa_pairs FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own qa_pairs"
  ON public.qa_pairs FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own qa_pairs"
  ON public.qa_pairs FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own qa_pairs"
  ON public.qa_pairs FOR DELETE
  USING (auth.uid() = user_id);

import { z } from 'zod';
import type { Tables } from '@/integrations/supabase/types';
import type { NexusDocument } from '@/types/nexus';

const kind = z.enum(['contract', 'tender', 'bid', 'product', 'proposal', 'invoice', 'other']).catch('other');
const extracted = z.object({
  client_name: z.string().optional(), amount: z.number().optional(),
  date: z.string().optional(), summary: z.string().optional(),
});

export function toDocument(row: Tables<'documents'>): NexusDocument {
  let data: unknown = row.extracted_data;
  if (typeof data === 'string') {
    try { data = JSON.parse(data); } catch { data = {}; }
  }
  const parsed = extracted.safeParse(data);
  return {
    id: row.id, name: row.name, doc_type: kind.parse(row.doc_type),
    created_at: row.created_at || '',
    status: row.status === 'ready' || row.status === 'completed' ? 'completed'
      : row.status === 'failed' || row.status === 'error' ? 'error' : 'processing',
    extracted_data: parsed.success ? parsed.data : {},
  };
}

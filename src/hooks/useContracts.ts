import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

export interface ContractEvent {
  id: string;
  contract_id: string;
  event_type: string;
  description: string;
  user_id?: string;
  created_at: string;
}

export interface Contract {
  id: string;
  organization_id: string;
  title: string;
  customer_id: string | null;
  customer_name?: string;
  contract_number: string;
  contract_type: string;
  status: string;
  amount: number | null;
  currency: string;
  start_date: string;
  end_date: string;
  signed_by: string | null;
  signed_at: string | null;
  document_url: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ContractWithEvents extends Contract {
  events: ContractEvent[];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const contractsTable = () => supabase.from('contracts') as any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const eventsTable = () => supabase.from('contract_events') as any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const customersTable = () => supabase.from('customers') as any;

/** Fetch all contracts for the current organization */
export function useContracts(filters?: { status?: string; search?: string }) {
  const { profile } = useAuth();
  const orgId = profile?.organization_id;

  return useQuery({
    queryKey: ['contracts', orgId, filters?.status, filters?.search],
    queryFn: async () => {
      let query = contractsTable()
        .select('*')
        .eq('organization_id', orgId)
        .order('created_at', { ascending: false });

      if (filters?.status && filters.status !== 'all') {
        query = query.eq('status', filters.status);
      }

      if (filters?.search) {
        query = query.or(
          `title.ilike.%${filters.search}%,contract_number.ilike.%${filters.search}%`
        );
      }

      const { data, error } = await query;
      if (error) throw error;

      // Resolve customer names via customer_id
      const contracts = (data || []) as Contract[];
      const customerIds = [...new Set(contracts.map(c => c.customer_id).filter(Boolean))];

      let customerMap: Record<string, string> = {};
      if (customerIds.length > 0) {
        const { data: customers } = await customersTable()
          .select('id, name')
          .in('id', customerIds);
        for (const c of (customers || [])) {
          customerMap[c.id] = c.name;
        }
      }

      return contracts.map(c => ({
        ...c,
        customer_name: c.customer_id ? customerMap[c.customer_id] || undefined : undefined,
        tags: c.tags || [],
      }));
    },
    enabled: !!orgId,
  });
}

/** Fetch a single contract with its events */
export function useContractDetail(contractId: string | null) {
  return useQuery({
    queryKey: ['contract-detail', contractId],
    queryFn: async () => {
      if (!contractId) return null;

      const { data: events, error } = await eventsTable()
        .select('*')
        .eq('contract_id', contractId)
        .order('created_at', { ascending: false });

      if (error) throw error;
      return (events || []) as ContractEvent[];
    },
    enabled: !!contractId,
  });
}

/** Create a new contract */
export function useCreateContract() {
  const queryClient = useQueryClient();
  const { user, profile } = useAuth();

  return useMutation({
    mutationFn: async (input: {
      title: string;
      customer_name?: string;
      contract_number?: string;
      contract_type: string;
      amount?: number | null;
      start_date?: string;
      end_date?: string;
    }) => {
      if (!profile?.organization_id) throw new Error('Organization ID missing');

      // If customer_name provided, try to find or create customer
      let customer_id: string | null = null;
      if (input.customer_name) {
        const { data: existing } = await customersTable()
          .select('id')
          .eq('organization_id', profile.organization_id)
          .ilike('name', input.customer_name)
          .limit(1);

        if (existing && existing.length > 0) {
          customer_id = existing[0].id;
        }
        // If no existing customer found, leave customer_id null
        // (creating customers is not this page's responsibility)
      }

      const { data, error } = await contractsTable()
        .insert({
          organization_id: profile.organization_id,
          title: input.title,
          customer_id,
          contract_number: input.contract_number || null,
          contract_type: input.contract_type,
          amount: input.amount || null,
          currency: 'CNY',
          start_date: input.start_date || null,
          end_date: input.end_date || null,
          status: 'draft',
          tags: [],
        })
        .select()
        .single();

      if (error) throw error;

      // Add "created" event
      await eventsTable().insert({
        contract_id: data.id,
        event_type: 'created',
        description: '合同创建',
        user_id: user?.id,
      });

      return data as Contract;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
    },
  });
}

/** Update contract status or fields */
export function useUpdateContract() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  return useMutation({
    mutationFn: async (input: {
      id: string;
      updates: Partial<Pick<Contract, 'title' | 'status' | 'amount' | 'start_date' | 'end_date' | 'contract_type' | 'tags'>>;
      eventDescription?: string;
    }) => {
      const { data, error } = await contractsTable()
        .update({ ...input.updates, updated_at: new Date().toISOString() })
        .eq('id', input.id)
        .select()
        .single();

      if (error) throw error;

      // If status changed, add an event
      if (input.updates.status && input.eventDescription) {
        const eventTypeMap: Record<string, string> = {
          pending_review: 'submitted',
          active: 'approved',
          expired: 'expired',
          terminated: 'terminated',
          renewed: 'renewed',
        };
        await eventsTable().insert({
          contract_id: input.id,
          event_type: eventTypeMap[input.updates.status] || 'amended',
          description: input.eventDescription,
          user_id: user?.id,
        });
      }

      return data as Contract;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] });
      queryClient.invalidateQueries({ queryKey: ['contract-detail'] });
    },
  });
}

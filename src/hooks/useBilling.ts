import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { aiClient } from '@/api/aiClient';
import { supabase } from '@/integrations/supabase/client';

export interface BillingPlan {
  id?: string;
  plan?: string;
  name: string;
  price?: number;
  price_monthly_usd?: number;
  yearly?: number;
  features: string[];
  popular?: boolean;
}

export interface Subscription {
  org_id: string;
  plan: string;
  status: string;
  current_period_end?: string | null;
  access_source?: 'default' | 'self_service' | 'admin_approved' | 'admin_override' | 'payment_provider';
  approved_at?: string | null;
  has_paid_access: boolean;
  is_expired: boolean;
  notice_policy: 'none' | 'action_required';
}

export interface SubscriptionAccessRequest {
  id: string;
  org_id: string;
  requested_plan: string;
  requested_days: number;
  note?: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  review_reason?: string | null;
  approved_expires_at?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export interface UsageStats {
  monthly_tokens_used: number;
  monthly_token_limit: number;
  daily_tokens_used: number;
  daily_token_limit: number;
  storage_used_mb: number;
  storage_limit_mb: number;
}

export function usePlans() {
  return useQuery({
    queryKey: ['billing', 'plans'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { plans: BillingPlan[] } }>('api/billing/plans');
      return res.data.plans;
    },
    staleTime: 30 * 60 * 1000,
  });
}

export function useSubscription() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['billing', 'subscription'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { subscription: Subscription | null } }>(
        'api/billing/subscription',
      );
      return res.data.subscription;
    },
    staleTime: 60 * 1000,
    refetchInterval: 2 * 60 * 1000,
    refetchOnReconnect: true,
    refetchOnWindowFocus: 'always',
    retry: 2,
  });

  useEffect(() => {
    const orgId = query.data?.org_id;
    if (!orgId) return undefined;
    const channel = supabase
      .channel(`billing-entitlement:${orgId}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'subscriptions', filter: `org_id=eq.${orgId}` },
        () => queryClient.invalidateQueries({ queryKey: ['billing'] }),
      )
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [query.data?.org_id, queryClient]);

  return query;
}

export function useLatestAccessRequest() {
  return useQuery({
    queryKey: ['billing', 'access-request'],
    queryFn: async () => {
      const res = await aiClient.fetch<{
        success: boolean;
        data: { request: SubscriptionAccessRequest | null };
      }>('api/billing/access-request');
      return res.data.request;
    },
    staleTime: 30 * 1000,
    refetchOnWindowFocus: 'always',
  });
}

export function useRequestAccess() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ plan, requestedDays, note }: { plan: string; requestedDays: number; note: string }) => {
      const res = await aiClient.fetch<{
        success: boolean;
        data: { request: SubscriptionAccessRequest };
      }>('api/billing/access-request', {
        method: 'POST',
        body: JSON.stringify({ plan, requested_days: requestedDays, note }),
      });
      return res.data.request;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['billing'] });
    },
  });
}

export function useUsageStats() {
  return useQuery({
    queryKey: ['billing', 'usage'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: UsageStats }>('api/billing/usage');
      return res.data;
    },
    refetchInterval: 5 * 60 * 1000,
  });
}

/** Compatibility hooks retained for existing payment-provider deployments. */
export function useSubscribe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (plan: string) => {
      const res = await aiClient.fetch<{ success: boolean; data: { subscription: Subscription } }>(
        'api/billing/subscribe',
        { method: 'POST', body: JSON.stringify({ plan }) },
      );
      return res.data.subscription;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['billing'] }),
  });
}

export function useCancelSubscription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { cancelled: boolean } }>('api/billing/cancel', {
        method: 'POST',
      });
      return res.data.cancelled;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['billing'] }),
  });
}

export function useCheckout() {
  return useMutation({
    mutationFn: async ({ planId, successUrl, cancelUrl }: { planId: string; successUrl: string; cancelUrl: string }) => {
      const res = await aiClient.fetch<{ success: boolean; data: { url: string; session_id: string } }>(
        'api/billing/checkout',
        {
          method: 'POST',
          body: JSON.stringify({ plan_id: planId, success_url: successUrl, cancel_url: cancelUrl }),
        },
      );
      return res.data;
    },
  });
}

export function useStartTrial() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (days = 14) => {
      const res = await aiClient.fetch<{ success: boolean; data: unknown }>('api/billing/trial', {
        method: 'POST',
        body: JSON.stringify({ days }),
      });
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['billing'] }),
  });
}

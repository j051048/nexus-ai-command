/**
 * Billing hooks — React Query 封装
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';

export interface BillingPlan {
  id: string;
  name: string;
  price: number;
  yearly?: number;
  features: string[];
  popular?: boolean;
}

export interface Subscription {
  org_id: string;
  plan: string;
  status: string;
  current_period_end?: string;
  stripe_customer_id?: string;
  trial_ends_at?: string;
}

export interface UsageStats {
  monthly_tokens_used: number;
  monthly_token_limit: number;
  daily_tokens_used: number;
  daily_token_limit: number;
  storage_used_mb: number;
  storage_limit_mb: number;
}

/** 获取计划目录 */
export function usePlans() {
  return useQuery({
    queryKey: ['billing', 'plans'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { plans: BillingPlan[] } }>('api/billing/plans');
      return res.data.plans;
    },
    staleTime: 1000 * 60 * 30, // 30 min
  });
}

/** 获取当前订阅 */
export function useSubscription() {
  return useQuery({
    queryKey: ['billing', 'subscription'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { subscription: Subscription | null } }>('api/billing/subscription');
      return res.data.subscription;
    },
  });
}

/** 获取用量统计 */
export function useUsageStats() {
  return useQuery({
    queryKey: ['billing', 'usage'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: UsageStats }>('api/billing/usage');
      return res.data;
    },
    refetchInterval: 1000 * 60 * 5, // 5 min
  });
}

/** 订阅计划 */
export function useSubscribe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (plan: string) => {
      const res = await aiClient.fetch<{ success: boolean; data: { subscription: Subscription } }>(
        'api/billing/subscribe',
        { method: 'POST', body: JSON.stringify({ plan }) }
      );
      return res.data.subscription;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['billing'] }),
  });
}

/** 取消订阅 */
export function useCancelSubscription() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { cancelled: boolean } }>(
        'api/billing/cancel',
        { method: 'POST' }
      );
      return res.data.cancelled;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['billing'] }),
  });
}

/** 创建 Stripe Checkout Session */
export function useCheckout() {
  return useMutation({
    mutationFn: async ({ planId, successUrl, cancelUrl }: { planId: string; successUrl: string; cancelUrl: string }) => {
      const res = await aiClient.fetch<{ success: boolean; data: { url: string; session_id: string } }>(
        'api/billing/checkout',
        { method: 'POST', body: JSON.stringify({ plan_id: planId, success_url: successUrl, cancel_url: cancelUrl }) }
      );
      return res.data;
    },
  });
}

/** 开始试用 */
export function useStartTrial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (days = 14) => {
      const res = await aiClient.fetch<{ success: boolean; data: unknown }>(
        'api/billing/trial',
        { method: 'POST', body: JSON.stringify({ days }) }
      );
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['billing'] }),
  });
}

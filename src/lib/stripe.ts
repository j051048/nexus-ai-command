import { getApiBaseUrl } from "@/lib/apiConfig";
/**
 * Stripe.js 初始化 + Checkout 辅助函数
 */
import { loadStripe, type Stripe } from '@stripe/stripe-js';

let stripePromise: Promise<Stripe | null> | null = null;

export function getStripe(): Promise<Stripe | null> {
  if (!stripePromise) {
    const key = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY;
    if (!key) {
      console.warn('[Stripe] VITE_STRIPE_PUBLISHABLE_KEY not set — Stripe disabled');
      stripePromise = Promise.resolve(null);
    } else {
      stripePromise = loadStripe(key);
    }
  }
  return stripePromise;
}

/** 重定向到 Stripe Checkout */
export async function redirectToCheckout(sessionId: string): Promise<void> {
  const stripe = await getStripe();
  if (!stripe) throw new Error('Stripe not initialized');
  const { error } = await stripe.redirectToCheckout({ sessionId });
  if (error) throw error;
}

/** 跳转到 Stripe 客户门户 */
export async function redirectToCustomerPortal(returnUrl: string): Promise<void> {
  // 后端需要提供 portal session endpoint
  const API_BASE = getApiBaseUrl();
  const res = await fetch(`${API_BASE}/api/billing/portal-session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ return_url: returnUrl }),
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to create portal session');
  const { data } = await res.json();
  window.location.href = data.url;
}

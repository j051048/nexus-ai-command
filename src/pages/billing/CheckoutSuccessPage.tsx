/**
 * Stripe Checkout 成功回调页
 */
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function CheckoutSuccessPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const sessionId = params.get('session_id');

  useEffect(() => {
    // 可在此验证 session 状态
  }, [sessionId]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <CheckCircle2 className="w-16 h-16 text-green-500" />
      <h1 className="text-2xl font-bold">支付成功</h1>
      <p className="text-muted-foreground">您的订阅已激活</p>
      {sessionId && (
        <p className="text-xs text-muted-foreground">Session: {sessionId}</p>
      )}
      <Button onClick={() => navigate('/billing')}>返回订阅管理</Button>
    </div>
  );
}

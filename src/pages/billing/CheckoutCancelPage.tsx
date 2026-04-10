/**
 * Stripe Checkout 取消回调页
 */
import { useNavigate } from 'react-router-dom';
import { XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function CheckoutCancelPage() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <XCircle className="w-16 h-16 text-muted-foreground" />
      <h1 className="text-2xl font-bold">支付已取消</h1>
      <p className="text-muted-foreground">您可以选择其他计划或稍后重试</p>
      <Button onClick={() => navigate('/billing')}>返回订阅管理</Button>
    </div>
  );
}

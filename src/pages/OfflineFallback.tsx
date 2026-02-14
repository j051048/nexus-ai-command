import React, { useState, useEffect } from 'react';
import { WifiOff, RefreshCw, CloudOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { offlineQueue } from '@/services/offlineQueue';

/**
 * React 版离线回退页面
 * 当应用已加载但 API 不可达时使用
 */
export const OfflineFallback: React.FC = () => {
  const [isRetrying, setIsRetrying] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    let mounted = true;

    const loadPendingCount = async () => {
      try {
        const count = await offlineQueue.getCount();
        if (mounted) setPendingCount(count);
      } catch {
        // IndexedDB may not be available
      }
    };

    loadPendingCount();

    const handleOnline = () => {
      if (mounted) window.location.reload();
    };
    window.addEventListener('online', handleOnline);

    return () => {
      mounted = false;
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      // Try a simple fetch to check connectivity
      const res = await fetch('/api/health', { method: 'GET', signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        window.location.reload();
        return;
      }
    } catch {
      // Still offline
    }
    setIsRetrying(false);
  };

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-6 p-8 text-center">
      <div className="relative">
        <CloudOff className="w-16 h-16 text-muted-foreground/50" />
        <WifiOff className="w-6 h-6 text-destructive absolute -bottom-1 -right-1" />
      </div>

      <div className="space-y-2">
        <h2 className="text-xl font-semibold text-foreground">
          网络连接不可用
        </h2>
        <p className="text-muted-foreground text-sm max-w-sm">
          部分功能在离线模式下可用。当网络恢复后，待同步的操作将自动提交。
        </p>
      </div>

      {pendingCount > 0 && (
        <div className="bg-muted/50 border rounded-lg px-4 py-3 text-sm">
          <span className="text-muted-foreground">待同步操作：</span>
          <span className="font-semibold text-foreground ml-1">{pendingCount} 项</span>
        </div>
      )}

      <Button
        onClick={handleRetry}
        disabled={isRetrying}
        className="gap-2"
      >
        <RefreshCw className={`w-4 h-4 ${isRetrying ? 'animate-spin' : ''}`} />
        {isRetrying ? '正在重连...' : '重新连接'}
      </Button>
    </div>
  );
};

export default OfflineFallback;

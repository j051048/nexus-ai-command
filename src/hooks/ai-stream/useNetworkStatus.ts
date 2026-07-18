import { useEffect, useState } from 'react';
import { toast } from 'sonner';

/** Keep weak-network status and its user feedback out of the stream runtime. */
export function useNetworkStatus(): boolean {
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    const handleOffline = () => {
      setIsOffline(true);
      toast.warning('网络已断开，AI 功能暂时不可用', {
        id: 'network-status',
        duration: Infinity,
      });
    };
    const handleOnline = () => {
      setIsOffline(false);
      toast.success('网络已恢复', { id: 'network-status', duration: 3000 });
    };
    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);
    return () => {
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  return isOffline;
}

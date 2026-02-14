import React, { useState, useEffect, useCallback } from 'react';
import { X, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';

/**
 * PWA 安装提示组件
 *
 * 监听 beforeinstallprompt 事件，显示底部固定横条提示用户安装。
 * 安装后或关闭后在 localStorage 标记已处理，不再显示。
 */

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const STORAGE_KEY = 'nexus-pwa-install-dismissed';

export const InstallPrompt: React.FC = () => {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isInstalling, setIsInstalling] = useState(false);

  useEffect(() => {
    // 检查是否已经处理过
    const dismissed = localStorage.getItem(STORAGE_KEY);
    if (dismissed) return;

    // 检查是否已经作为 PWA 安装运行
    if (window.matchMedia('(display-mode: standalone)').matches) return;

    const handleBeforeInstall = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setIsVisible(true);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);

    // 监听安装完成
    const handleAppInstalled = () => {
      setIsVisible(false);
      setDeferredPrompt(null);
      localStorage.setItem(STORAGE_KEY, 'installed');
    };

    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return;

    setIsInstalling(true);
    try {
      await deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;

      if (outcome === 'accepted') {
        localStorage.setItem(STORAGE_KEY, 'installed');
      } else {
        localStorage.setItem(STORAGE_KEY, 'dismissed');
      }
    } catch (err) {
      console.warn('Install prompt error:', err);
    } finally {
      setIsInstalling(false);
      setIsVisible(false);
      setDeferredPrompt(null);
    }
  }, [deferredPrompt]);

  const handleDismiss = useCallback(() => {
    setIsVisible(false);
    setDeferredPrompt(null);
    localStorage.setItem(STORAGE_KEY, 'dismissed');
  }, []);

  if (!isVisible) return null;

  return (
    <div className="fixed bottom-16 md:bottom-4 left-4 right-4 z-50 animate-in slide-in-from-bottom-4 duration-300">
      <div className="max-w-lg mx-auto bg-card border border-border rounded-lg shadow-xl px-4 py-3 flex items-center gap-3">
        <div className="flex-shrink-0">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Download className="w-5 h-5 text-primary" />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">
            安装 Nexus AI 到桌面
          </p>
          <p className="text-xs text-muted-foreground">
            更快的访问速度，离线可用
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <Button
            size="sm"
            onClick={handleInstall}
            disabled={isInstalling}
            className="h-8 px-3 text-xs"
          >
            {isInstalling ? '安装中...' : '安装'}
          </Button>
          <button
            onClick={handleDismiss}
            className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            aria-label="关闭安装提示"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default InstallPrompt;

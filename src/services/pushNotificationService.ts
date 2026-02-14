/**
 * Web Push 推送通知前端服务
 *
 * 负责:
 * - 获取 VAPID 公钥
 * - 请求通知权限
 * - 订阅/取消订阅 PushManager
 * - 与后端同步订阅信息
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

class PushNotificationService {
  private registration: ServiceWorkerRegistration | null = null;
  private vapidKey: string | null = null;

  /**
   * 初始化：等待 Service Worker 就绪
   */
  async init(): Promise<void> {
    if (!this.isSupported()) return;

    try {
      this.registration = await navigator.serviceWorker.ready;
    } catch (err) {
      console.warn('Service Worker not ready for push:', err);
    }
  }

  /**
   * 检查浏览器是否支持 Web Push
   */
  isSupported(): boolean {
    return 'serviceWorker' in navigator && 'PushManager' in window;
  }

  /**
   * 获取当前通知权限状态
   */
  async getPermissionState(): Promise<NotificationPermission> {
    if (!('Notification' in window)) return 'denied';
    return Notification.permission;
  }

  /**
   * 从后端获取 VAPID 公钥
   */
  async getVapidKey(): Promise<string | null> {
    if (this.vapidKey) return this.vapidKey;

    try {
      const cleanBase = API_BASE.replace(/\/$/, '');
      const res = await fetch(`${cleanBase}/api/push/vapid-key`);
      if (!res.ok) return null;

      const json = await res.json();
      const key = json.data?.vapid_key || null;
      if (key) this.vapidKey = key;
      return key;
    } catch (err) {
      console.warn('Failed to fetch VAPID key:', err);
      return null;
    }
  }

  /**
   * 订阅推送通知
   * 1. 获取 VAPID key
   * 2. 请求通知权限
   * 3. 通过 PushManager 订阅
   * 4. 将 subscription 发送到后端
   */
  async subscribe(): Promise<boolean> {
    if (!this.isSupported() || !this.registration) {
      await this.init();
    }
    if (!this.registration) return false;

    // 1. Get VAPID key
    const vapidKey = await this.getVapidKey();
    if (!vapidKey) {
      console.warn('Push: No VAPID key available');
      return false;
    }

    // 2. Request notification permission
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      console.info('Push: Permission denied by user');
      return false;
    }

    // 3. Subscribe via PushManager
    try {
      const subscription = await this.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });

      // 4. Send subscription to backend
      const cleanBase = API_BASE.replace(/\/$/, '');
      const res = await fetch(`${cleanBase}/api/push/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscription: subscription.toJSON() }),
      });

      return res.ok;
    } catch (err) {
      console.error('Push subscription failed:', err);
      return false;
    }
  }

  /**
   * 取消推送订阅
   */
  async unsubscribe(): Promise<void> {
    if (!this.registration) return;

    try {
      const subscription = await this.registration.pushManager.getSubscription();
      if (!subscription) return;

      // Unsubscribe from PushManager
      await subscription.unsubscribe();

      // Notify backend
      const cleanBase = API_BASE.replace(/\/$/, '');
      await fetch(`${cleanBase}/api/push/unsubscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: subscription.endpoint }),
      });
    } catch (err) {
      console.warn('Push unsubscribe failed:', err);
    }
  }

  /**
   * 检查当前是否已订阅
   */
  async isSubscribed(): Promise<boolean> {
    if (!this.registration) return false;

    try {
      const subscription = await this.registration.pushManager.getSubscription();
      return subscription !== null;
    } catch {
      return false;
    }
  }
}

export const pushNotificationService = new PushNotificationService();

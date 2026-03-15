import { useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';
import { enqueueProactiveMessage } from '@/lib/proactiveMessageStore';

/**
 * WebSocket 实时推送 hook
 *
 * 连接后端 /ws/push 端点，接收服务器推送的通知。
 * 收到通知后自动 invalidate React Query 缓存触发 UI 刷新，
 * 并用 toast 弹出提示。
 *
 * 特性：
 * - 自动认证（通过 Supabase JWT）
 * - 指数退避重连（1s → 2s → 4s → ... → 30s）
 * - 心跳保活（每 25 秒发送 ping）
 * - 组件卸载时优雅断开
 * - 防重复连接（connect 前关闭已有连接）
 */

// Close codes that should NOT trigger reconnection
const NO_RECONNECT_CODES = new Set([
  1013, // Server at capacity / too many connections per user
  4001, // Authentication failure
  4002, // Evicted by server (newer connection exists)
  4003, // Heartbeat timeout (stale connection)
]);

export function useWebSocketPush() {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval>>();
  const reconnectAttemptRef = useRef(0);
  const unmountedRef = useRef(false);
  // Guard against visibility-triggered close racing with onclose reconnect
  const intentionalCloseRef = useRef(false);

  const connect = useCallback(async () => {
    if (unmountedRef.current) return;

    // Close existing connection before creating a new one
    if (wsRef.current) {
      const existing = wsRef.current;
      wsRef.current = null;
      intentionalCloseRef.current = true;
      if (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING) {
        existing.close(4001, 'Superseded by new connect call');
      }
    }

    // 获取 JWT token
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token;
    if (!token) {
      // 未登录，稍后重试
      scheduleReconnect();
      return;
    }

    // 构造 WebSocket URL
    let baseUrl = import.meta.env.VITE_API_BASE_URL || '';
    if (!baseUrl) return;

    // 将 http(s) 转换为 ws(s)
    baseUrl = baseUrl.replace(/\/$/, '');
    if (baseUrl.startsWith('https://')) {
      baseUrl = 'wss://' + baseUrl.slice(8);
    } else if (baseUrl.startsWith('http://')) {
      baseUrl = 'ws://' + baseUrl.slice(7);
    } else if (baseUrl.includes('localhost') || baseUrl.includes('127.0.0.1')) {
      baseUrl = 'ws://' + baseUrl;
    } else {
      baseUrl = 'wss://' + baseUrl;
    }

    const wsUrl = `${baseUrl}/ws/push?token=${encodeURIComponent(token)}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptRef.current = 0;
        console.log('[WS Push] Connected');

        // 启动心跳
        heartbeatTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 25_000);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === 'pong') return; // 心跳响应

          // Reply to server-initiated ping
          if (msg.type === 'ping') {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'pong' }));
            }
            return;
          }

          if (msg.type === 'notification') {
            // 刷新通知列表和未读数
            queryClient.invalidateQueries({ queryKey: ['notification-center'] });
            queryClient.invalidateQueries({ queryKey: ['notification-unread-count'] });

            // Toast 提示
            const data = msg.data;
            if (data?.title) {
              toast.info(data.title, {
                description: data.content?.slice(0, 100),
                duration: 5000,
              });
            }
          }

          // P0-1: AI 主动发起聊天对话
          if (msg.type === 'proactive_chat') {
            const { session_id, title, message, priority } = msg.data;

            // 入队 → ChatPanel 自动消费并显示在对话列表中
            enqueueProactiveMessage({
              sessionId: session_id,
              title,
              message,
              priority,
              receivedAt: new Date(),
            });

            // Toast 通知（移动端面板关闭时的备用入口）
            toast.info(title, {
              description: message?.slice(0, 100),
              action: {
                label: '打开对话',
                onClick: () => {
                  window.dispatchEvent(new CustomEvent('proactive-chat', {
                    detail: { session_id, title, message }
                  }));
                },
              },
              duration: priority === 'urgent' ? 30000 : 15000,
            });
          }

          // P0-2: 智能推荐主动推送
          if (msg.type === 'recommendation') {
            const recs = msg.data as Array<{
              title: string; description: string;
              action_url?: string; action_label?: string; priority: string;
            }>;
            const top = recs?.[0];
            if (top) {
              toast.info(top.title, {
                description: top.description?.slice(0, 100),
                duration: 10000,
              });
            }
            queryClient.invalidateQueries({ queryKey: ['smart-recommendations'] });
          }
        } catch {
          // 忽略解析失败
        }
      };

      ws.onclose = (event) => {
        console.log(`[WS Push] Closed (code=${event.code})`);
        cleanup();

        // Don't reconnect if:
        // - component unmounted
        // - server explicitly told us not to (4001/4002/4003)
        // - we intentionally closed this connection (visibility change / superseded)
        if (unmountedRef.current || NO_RECONNECT_CODES.has(event.code) || intentionalCloseRef.current) {
          intentionalCloseRef.current = false;
          return;
        }
        scheduleReconnect();
      };

      ws.onerror = () => {
        // onclose 会随后触发，在那里处理重连
      };
    } catch {
      scheduleReconnect();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryClient]);

  const cleanup = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = undefined;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (unmountedRef.current) return;

    const attempt = reconnectAttemptRef.current;
    const delay = Math.min(1000 * Math.pow(2, attempt), 30_000);
    reconnectAttemptRef.current = attempt + 1;

    console.log(`[WS Push] Reconnecting in ${delay}ms (attempt ${attempt + 1})`);
    reconnectTimerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    // Page Visibility API：后台时断开 WS 省电，前台时重连
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        // 进入后台：主动断开，停止心跳
        if (reconnectTimerRef.current) {
          clearTimeout(reconnectTimerRef.current);
        }
        cleanup();
        if (wsRef.current) {
          intentionalCloseRef.current = true;
          wsRef.current.close();
          wsRef.current = null;
        }
      } else {
        // 回到前台：立即重连 + 刷新数据
        reconnectAttemptRef.current = 0;
        connect();
        queryClient.invalidateQueries({ queryKey: ['notification-center'] });
        queryClient.invalidateQueries({ queryKey: ['notification-unread-count'] });
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      unmountedRef.current = true;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      cleanup();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, cleanup]);
}

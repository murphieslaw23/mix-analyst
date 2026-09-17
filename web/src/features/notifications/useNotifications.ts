import { useCallback, useEffect, useRef, useState } from 'react';
import { authHeaders } from '../../api';
import { apiClient, type ApiProblem } from '../../api/client';

export interface NotificationItem {
  id: string;
  job_id: string | null;
  kind: string;
  deep_link: string;
  status: string;
  created_at: string;
  read_at: string | null;
}

export type NotificationsPhase = 'loading' | 'ready' | 'error';

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

export function notificationProblemMessage(problem: unknown): string {
  const record = problem as Partial<ApiProblem> | null;
  if (record && typeof record.detail === 'string' && record.detail.length > 0) {
    return record.detail;
  }
  if (record && typeof record.title === 'string' && record.title.length > 0) {
    return record.title;
  }
  if (problem instanceof Error && problem.message) return problem.message;
  return 'Request failed';
}

export interface UseNotificationsResult {
  items: NotificationItem[];
  unreadCount: number;
  phase: NotificationsPhase;
  error: string | null;
  liveMessage: string;
  toast: NotificationItem | null;
  refresh: () => void;
  markRead: (id: string) => Promise<void>;
  dismiss: (id: string) => Promise<void>;
  actionPending: string | null;
  actionError: string | null;
}

/**
 * Durable notification center client (PWA plan Task 3 frontend).
 * State lives in PostgreSQL; this hook renders authoritative API state and
 * persists read/dismiss across reloads. Local cache is rendering-only.
 */
export function useNotifications(): UseNotificationsResult {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [phase, setPhase] = useState<NotificationsPhase>('loading');
  const [error, setError] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [liveMessage, setLiveMessage] = useState('Notifications view loaded.');
  const itemsRef = useRef<NotificationItem[]>([]);
  itemsRef.current = items;

  const fetchOnce = useCallback(async (): Promise<NotificationItem[]> => {
    const fresh = await apiClient<NotificationItem[]>('/notifications', {
      headers: { ...mutationHeaders() },
    });
    const list = Array.isArray(fresh) ? fresh : [];
    setItems(list);
    return list;
  }, []);

  const refresh = useCallback(() => {
    setError(null);
    void fetchOnce()
      .then((list) => {
        setPhase('ready');
        const unread = list.filter(
          (n) => !n.read_at && (n.status || '').toLowerCase() === 'unread',
        ).length;
        setLiveMessage(
          `Notifications view loaded. ${list.length} notifications, ${unread} unread.`,
        );
      })
      .catch((err: unknown) => {
        setError(notificationProblemMessage(err));
        setPhase((prev) => (itemsRef.current.length > 0 ? prev : 'error'));
        setLiveMessage('Notifications could not be loaded.');
      });
  }, [fetchOnce]);

  useEffect(() => {
    let cancelled = false;
    setPhase('loading');
    setError(null);
    void fetchOnce()
      .then((list) => {
        if (cancelled) return;
        setPhase('ready');
        const unread = list.filter(
          (n) => !n.read_at && (n.status || '').toLowerCase() === 'unread',
        ).length;
        setLiveMessage(
          `Notifications view loaded. ${list.length} notifications, ${unread} unread.`,
        );
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(notificationProblemMessage(err));
        setPhase('error');
        setLiveMessage('Notifications could not be loaded.');
      });

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        void fetchOnce().catch(() => {
          // Keep last authoritative list on transient failures.
        });
      }
    };
    document.addEventListener('visibilitychange', onVisibility);

    // Cross-tab invalidation without ever treating storage as the ledger.
    let channel: BroadcastChannel | null = null;
    try {
      if (typeof BroadcastChannel !== 'undefined') {
        channel = new BroadcastChannel('syco-notifications');
        channel.onmessage = () => {
          void fetchOnce().catch(() => undefined);
        };
      }
    } catch {
      channel = null;
    }
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisibility);
      try {
        channel?.close();
      } catch {
        // Channel teardown is best-effort.
      }
    };
  }, [fetchOnce]);

  const markRead = useCallback(
    async (id: string): Promise<void> => {
      setActionPending(id);
      setActionError(null);
      try {
        const updated = await apiClient<NotificationItem>(
          `/notifications/${encodeURIComponent(id)}/read`,
          { method: 'POST', headers: { ...mutationHeaders() }, body: JSON.stringify({}) },
        );
        setItems((prev) => prev.map((n) => (n.id === id ? updated : n)));
        setLiveMessage(`Notification ${id} marked as read.`);
      } catch (err) {
        setActionError(notificationProblemMessage(err));
      } finally {
        setActionPending(null);
      }
    },
    [],
  );

  const dismiss = useCallback(
    async (id: string): Promise<void> => {
      setActionPending(id);
      setActionError(null);
      try {
        const updated = await apiClient<NotificationItem>(
          `/notifications/${encodeURIComponent(id)}/dismiss`,
          { method: 'POST', headers: { ...mutationHeaders() }, body: JSON.stringify({}) },
        );
        setItems((prev) => prev.map((n) => (n.id === id ? updated : n)));
        setLiveMessage(`Notification ${id} dismissed.`);
      } catch (err) {
        setActionError(notificationProblemMessage(err));
      } finally {
        setActionPending(null);
      }
    },
    [],
  );

  const unreadCount = items.filter(
    (n) => !n.read_at && (n.status || '').toLowerCase() === 'unread',
  ).length;
  const toast =
    items.find((n) => !n.read_at && (n.status || '').toLowerCase() === 'unread') ?? null;

  return {
    items,
    unreadCount,
    phase,
    error,
    liveMessage,
    toast,
    refresh,
    markRead,
    dismiss,
    actionPending,
    actionError,
  };
}

export default useNotifications;

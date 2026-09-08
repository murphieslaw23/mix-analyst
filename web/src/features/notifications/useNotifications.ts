import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, asApiProblem, type ApiProblem } from "../../api/client";

export interface NotificationDto {
  id: string;
  job_id: string | null;
  kind: string;
  title: string;
  body: string | null;
  deep_link: string;
  read_at: string | null;
  dismissed_at: string | null;
  created_at: string;
}

interface NotificationListResponse {
  items: NotificationDto[];
  total: number;
}

const notificationChannelName = "syco23-notifications";

export function useNotifications() {
  const [items, setItems] = useState<NotificationDto[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ApiProblem | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set());
  const [retryKey, setRetryKey] = useState(0);
  const channelRef = useRef<BroadcastChannel | null>(null);

  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const channel = new BroadcastChannel(notificationChannelName);
    channelRef.current = channel;
    channel.onmessage = (event) => {
      if (event.data === "invalidate") setRetryKey((value) => value + 1);
    };
    return () => {
      channel.close();
      channelRef.current = null;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setProblem(null);
    void apiClient<NotificationListResponse>("/notifications", { signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return;
        setItems(response.items.filter((item) => item.dismissed_at === null));
        setTotal(response.total);
        setLoading(false);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setProblem(asApiProblem(error));
        setLoading(false);
      });
    return () => controller.abort();
  }, [retryKey]);

  const retry = useCallback(() => setRetryKey((value) => value + 1), []);

  const mutate = useCallback(async (id: string, action: "read" | "dismiss") => {
    setMutationError(null);
    setPendingIds((current) => {
      const next = new Set(current);
      next.add(id);
      return next;
    });
    try {
      const updated = await apiClient<NotificationDto>(`/notifications/${id}/${action}`, { method: "POST" });
      if (action === "dismiss") {
        setItems((current) => current.filter((item) => item.id !== id));
        setTotal((current) => Math.max(0, current - 1));
      } else {
        setItems((current) => current.map((item) => (item.id === id ? updated : item)));
      }
      channelRef.current?.postMessage("invalidate");
    } catch (error) {
      setMutationError(asApiProblem(error).detail);
    } finally {
      setPendingIds((current) => {
        const next = new Set(current);
        next.delete(id);
        return next;
      });
    }
  }, []);

  const markRead = useCallback((id: string) => mutate(id, "read"), [mutate]);
  const dismiss = useCallback((id: string) => mutate(id, "dismiss"), [mutate]);

  return { items, total, loading, problem, mutationError, pendingIds, retry, markRead, dismiss };
}

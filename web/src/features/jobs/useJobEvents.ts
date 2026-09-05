import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, apiUrl, asApiProblem, type ApiProblem } from "../../api/client";
import type { JobDto } from "../../api/contracts";
import { asJobDto, isTerminalStatus, toJobViewModel, type JobViewModel } from "./jobAdapters";

type ResourceState =
  | { status: "loading"; job: null; problem: null }
  | { status: "ready"; job: JobViewModel; problem: null }
  | { status: "error"; job: null; problem: ApiProblem };

type ConnectionMode = "connecting" | "live" | "polling" | "closed";

interface ParsedSseEvent {
  id: number | null;
  data: string;
}

const POLL_INTERVAL_MS = 5_000;
const RECONNECT_INTERVAL_MS = 5_000;

function cursorStorageKey(jobId: string) {
  return `syco23:job-event-cursor:${jobId}`;
}

function readCursor(jobId: string): number {
  const value = window.sessionStorage.getItem(cursorStorageKey(jobId));
  const parsed = value === null ? 0 : Number.parseInt(value, 10);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function saveCursor(jobId: string, cursor: number) {
  if (Number.isSafeInteger(cursor) && cursor >= 0) {
    window.sessionStorage.setItem(cursorStorageKey(jobId), String(cursor));
  }
}

function parseEventBlock(block: string): ParsedSseEvent | null {
  let id: number | null = null;
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("id:")) {
      const candidate = Number.parseInt(line.slice(3).trim(), 10);
      if (Number.isSafeInteger(candidate) && candidate >= 0) id = candidate;
    }
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  return data.length > 0 ? { id, data: data.join("\n") } : null;
}

/**
 * Read the API SSE endpoint with fetch rather than EventSource. The endpoint
 * authorizes cookies and accepts its replay cursor only in `Last-Event-ID`;
 * native EventSource cannot add that header for an explicit reconnect. Each
 * received event is only a wake-up: `GET /jobs/:id` stays authoritative.
 */
async function consumeSse(
  jobId: string,
  cursor: number,
  signal: AbortSignal,
  onEvent: (event: ParsedSseEvent) => void,
): Promise<void> {
  const headers = new Headers({ Accept: "text/event-stream" });
  if (cursor > 0) headers.set("Last-Event-ID", String(cursor));
  const response = await fetch(apiUrl(`/jobs/${encodeURIComponent(jobId)}/events`), {
    credentials: "include",
    headers,
    signal,
  });
  if (!response.ok || response.body === null) {
    throw new Error(`Job event stream unavailable (${response.status}).`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (!signal.aborted) {
      const next = await reader.read();
      if (next.done) return;
      buffer += decoder.decode(next.value, { stream: true });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const event = parseEventBlock(block);
        if (event) onEvent(event);
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
}

export function useJobEvents(jobId: string | undefined) {
  const [resource, setResource] = useState<ResourceState>({ status: "loading", job: null, problem: null });
  const [connection, setConnection] = useState<ConnectionMode>("connecting");
  const [actionProblem, setActionProblem] = useState<ApiProblem | null>(null);
  const [actionPending, setActionPending] = useState(false);
  const [streamVersion, setStreamVersion] = useState(0);
  const mounted = useRef(false);
  const requestVersion = useRef(0);

  const refresh = useCallback(async (signal?: AbortSignal): Promise<JobViewModel | null> => {
    if (!jobId) return null;
    const version = ++requestVersion.current;
    try {
      const response = await apiClient<unknown>(`/jobs/${encodeURIComponent(jobId)}`, { signal });
      const job = toJobViewModel(asJobDto(response));
      if (mounted.current && !signal?.aborted && version === requestVersion.current) {
        setResource({ status: "ready", job, problem: null });
      }
      return job;
    } catch (error) {
      if (mounted.current && !signal?.aborted && version === requestVersion.current) {
        setResource({ status: "error", job: null, problem: asApiProblem(error) });
      }
      return null;
    }
  }, [jobId]);

  useEffect(() => {
    mounted.current = true;
    if (!jobId) {
      setConnection("closed");
      setResource({ status: "error", job: null, problem: { status: 404, title: "Job not found", detail: "This job does not have a valid address.", retryable: false } });
      return () => { mounted.current = false; };
    }

    const controller = new AbortController();
    let pollTimer: number | undefined;
    let reconnectTimer: number | undefined;
    let disposed = false;

    const clearRecoveryTimers = () => {
      if (pollTimer !== undefined) window.clearInterval(pollTimer);
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      pollTimer = undefined;
      reconnectTimer = undefined;
    };

    const refreshAuthoritatively = async () => refresh(controller.signal);

    const fallBackToPolling = () => {
      if (disposed || controller.signal.aborted) return;
      setConnection("polling");
      if (pollTimer === undefined) {
        pollTimer = window.setInterval(() => { void refreshAuthoritatively(); }, POLL_INTERVAL_MS);
      }
      if (reconnectTimer === undefined) {
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = undefined;
          void startStream();
        }, RECONNECT_INTERVAL_MS);
      }
    };

    const startStream = async () => {
      if (disposed || controller.signal.aborted) return;
      clearRecoveryTimers();
      setConnection("connecting");
      const current = await refreshAuthoritatively();
      if (disposed || controller.signal.aborted || current === null) {
        if (!disposed && !controller.signal.aborted) fallBackToPolling();
        return;
      }
      if (isTerminalStatus(current.status)) {
        setConnection("closed");
        return;
      }
      try {
        setConnection("live");
        await consumeSse(jobId, readCursor(jobId), controller.signal, (event) => {
          if (event.id !== null) saveCursor(jobId, event.id);
          // Even valid JSON from the stream is deliberately not merged into UI
          // state. A GET observes the current attempt after retry/cancellation.
          void refreshAuthoritatively();
        });
        const afterClose = await refreshAuthoritatively();
        if (!disposed && !controller.signal.aborted && afterClose && !isTerminalStatus(afterClose.status)) fallBackToPolling();
        else if (!disposed && !controller.signal.aborted) setConnection("closed");
      } catch {
        if (!disposed && !controller.signal.aborted) fallBackToPolling();
      }
    };

    void startStream();
    return () => {
      disposed = true;
      controller.abort();
      clearRecoveryTimers();
      mounted.current = false;
    };
  }, [jobId, refresh, streamVersion]);

  const runAction = useCallback(async (action: "cancel" | "retry") => {
    if (!jobId || actionPending) return;
    setActionPending(true);
    setActionProblem(null);
    try {
      const response = await apiClient<unknown>(`/jobs/${encodeURIComponent(jobId)}/${action}`, { method: "POST" });
      const job = toJobViewModel(asJobDto(response as JobDto));
      if (mounted.current) setResource({ status: "ready", job, problem: null });
      // A retry creates a new attempt. Restarting refreshes state before its
      // replay cursor is used, preventing an old terminal event from winning.
      setStreamVersion((version) => version + 1);
    } catch (error) {
      if (mounted.current) setActionProblem(asApiProblem(error));
    } finally {
      if (mounted.current) setActionPending(false);
    }
  }, [actionPending, jobId]);

  const retry = useCallback(async () => { await runAction("retry"); }, [runAction]);
  const cancel = useCallback(async () => { await runAction("cancel"); }, [runAction]);
  const retryLoad = useCallback(() => {
    setResource({ status: "loading", job: null, problem: null });
    setStreamVersion((version) => version + 1);
  }, []);

  return {
    ...resource,
    connection,
    reconnecting: connection === "connecting" || connection === "polling",
    actionPending,
    actionProblem,
    cancel,
    retry,
    retryLoad,
  };
}

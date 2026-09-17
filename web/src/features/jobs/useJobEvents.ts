/**
 * Durable job event client (Task 4): SSE-first with polling fallback.
 *
 * Consumes GET /jobs/:jobId for authoritative state and
 * GET /jobs/:jobId/events as an SSE stream. The latest event id is persisted
 * per job (localStorage cursor) and resumed via Last-Event-ID; when the
 * stream is unavailable or ends without a terminal event, timed GET polling
 * takes over. Cancel/retry are semantic POST commands followed by a refresh.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { authHeaders } from '../../api';
import { API_BASE_URL, apiClient, type ApiProblem } from '../../api/client';

export interface StageRunView {
  id: string;
  stage_name: string;
  status: string;
  progress_percent: number;
  error_message?: string | null;
}

export interface JobViewModel {
  id: string;
  mix_id: string;
  job_type: string;
  status: string;
  progress_percent: number;
  current_stage?: string | null;
  error_message?: string | null;
  stage_runs?: StageRunView[];
}

export type JobPhase = 'loading' | 'live' | 'polling' | 'done' | 'error';

const TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED']);
const POLL_INTERVAL_MS = 2000;

function isTerminal(status: string | undefined | null): boolean {
  return TERMINAL.has((status || '').toUpperCase());
}

function cursorKey(jobId: string): string {
  return `syco_job_cursor_${jobId}`;
}

function loadCursor(jobId: string): number {
  try {
    const raw = localStorage.getItem(cursorKey(jobId));
    const parsed = raw === null ? 0 : Number.parseInt(raw, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
  } catch {
    return 0;
  }
}

function saveCursor(jobId: string, id: number): void {
  try {
    localStorage.setItem(cursorKey(jobId), String(id));
  } catch {
    // Cursor is a reconnect optimization only — never break the stream.
  }
}

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

export function jobProblemMessage(problem: unknown): string {
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

interface SseHandlers {
  signal: AbortSignal;
  onUpdate: (job: Partial<JobViewModel>) => void;
  onClose: () => void;
}

/** Read one SSE response body, dispatching update/close frames. */
async function readSseStream(
  response: Response,
  jobId: string,
  handlers: SseHandlers,
): Promise<'closed' | 'ended'> {
  const body = response.body;
  if (!body) return 'ended';
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const result: { outcome: 'closed' | 'ended' } = { outcome: 'ended' };

  const dispatchFrame = (frame: string) => {
    let eventName = 'message';
    const dataLines: string[] = [];
    let frameId: number | null = null;
    for (const rawLine of frame.split('\n')) {
      const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine;
      if (line.startsWith(':')) continue;
      if (line.startsWith('id:')) {
        const parsed = Number.parseInt(line.slice(3).trim(), 10);
        if (Number.isFinite(parsed)) frameId = parsed;
        continue;
      }
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
        continue;
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).startsWith(' ') ? line.slice(6) : line.slice(5));
      }
    }
    if (frameId !== null) saveCursor(jobId, frameId);
    if (dataLines.length === 0) return;
    const data = dataLines.join('\n');
    if (eventName === 'update') {
      try {
        handlers.onUpdate(JSON.parse(data) as Partial<JobViewModel>);
      } catch {
        // Ignore malformed frames; the next poll recovers authority.
      }
    } else if (eventName === 'close') {
      try {
        const payload = JSON.parse(data) as { status?: string };
        if (typeof payload.status === 'string') {
          handlers.onUpdate({ status: payload.status });
        }
      } catch {
        // Close frame without a parsable body still ends the stream.
      }
      result.outcome = 'closed';
    }
    // 'connect' and unknown events carry no state — ignore.
  };

  for (;;) {
    if (handlers.signal.aborted) break;
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      dispatchFrame(frame);
      if (result.outcome === 'closed' || handlers.signal.aborted) break;
      boundary = buffer.indexOf('\n\n');
    }
    if (result.outcome === 'closed' || handlers.signal.aborted) break;
  }
  try {
    reader.releaseLock();
  } catch {
    // Reader already released — nothing to do.
  }
  return result.outcome;
}

export interface UseJobEventsResult {
  job: JobViewModel | null;
  phase: JobPhase;
  /** True while polling after the live stream dropped (announced politely). */
  reconnecting: boolean;
  error: string | null;
  refresh: () => void;
  cancel: () => Promise<void>;
  retry: () => Promise<void>;
  actionError: string | null;
  actionPending: boolean;
}

export function useJobEvents(jobId: string): UseJobEventsResult {
  const [job, setJob] = useState<JobViewModel | null>(null);
  const [phase, setPhase] = useState<JobPhase>('loading');
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState(false);
  const jobRef = useRef<JobViewModel | null>(null);
  jobRef.current = job;
  const phaseRef = useRef<JobPhase>(phase);
  phaseRef.current = phase;

  const fetchOnce = useCallback(async (): Promise<JobViewModel | null> => {
    const fresh = await apiClient<JobViewModel>(`/jobs/${encodeURIComponent(jobId)}`, {
      headers: { ...mutationHeaders() },
    });
    setJob(fresh);
    return fresh;
  }, [jobId]);

  const refresh = useCallback(() => {
    setError(null);
    void fetchOnce()
      .then((fresh) => {
        if (fresh && isTerminal(fresh.status)) setPhase('done');
      })
      .catch((err: unknown) => setError(jobProblemMessage(err)));
  }, [fetchOnce]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    void (async () => {
      try {
        const initial = await apiClient<JobViewModel>(
          `/jobs/${encodeURIComponent(jobId)}`,
          { headers: { ...mutationHeaders() }, signal: controller.signal },
        );
        if (cancelled) return;
        setJob(initial);
        if (isTerminal(initial.status)) {
          setPhase('done');
          return;
        }
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        setError(jobProblemMessage(err));
        setPhase('error');
        return;
      }

      // SSE-first: resume from the persisted cursor.
      const cursor = loadCursor(jobId);
      try {
        const stream = await fetch(`${API_BASE_URL}/jobs/${encodeURIComponent(jobId)}/events`, {
          headers: {
            ...mutationHeaders(),
            Accept: 'text/event-stream',
            ...(cursor > 0 ? { 'Last-Event-ID': String(cursor) } : {}),
          },
          credentials: 'include',
          signal: controller.signal,
        });
        if (!stream.ok || !stream.body) throw new Error(`Event stream unavailable (${stream.status})`);
        if (cancelled) return;
        setPhase('live');
        const outcome = await readSseStream(stream, jobId, {
          signal: controller.signal,
          onUpdate: (patch) =>
            setJob((prev) => ({ ...(prev as JobViewModel), ...patch }) as JobViewModel),
          onClose: () => {},
        });
        if (cancelled) return;
        const latest = jobRef.current;
        if (outcome === 'closed' || (latest && isTerminal(latest.status))) {
          // Authoritative confirmation before settling a terminal state.
          try {
            const confirmed = await fetchOnce();
            if (cancelled) return;
            if (confirmed && isTerminal(confirmed.status)) {
              setPhase('done');
              return;
            }
          } catch {
            // Fall through to polling when confirmation fails.
          }
          if (cancelled) return;
          if (jobRef.current && isTerminal(jobRef.current.status)) {
            setPhase('done');
            return;
          }
        }
        // Stream dropped without a terminal state: reconnect semantics are
        // one authoritative refresh, then timed polling (owned by the
        // polling effect below).
        try {
          const refreshed = await fetchOnce();
          if (cancelled) return;
          if (refreshed && isTerminal(refreshed.status)) {
            setPhase('done');
            return;
          }
        } catch {
          // Polling retries on its own tick.
        }
        if (!cancelled) setPhase('polling');
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        void err;
        if (!cancelled) setPhase('polling');
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [jobId, fetchOnce]);

  // Polling fallback: active only while flagged. Stops on terminal states.
  useEffect(() => {
    if (phase !== 'polling') return;
    if (job && isTerminal(job.status)) {
      setPhase('done');
      return;
    }
    const tick = () => {
      void fetchOnce()
        .then((fresh) => {
          if (fresh && isTerminal(fresh.status)) setPhase('done');
        })
        .catch(() => {
          // Backend unreachable — leave last known state in place.
        });
    };
    const poller = window.setInterval(tick, POLL_INTERVAL_MS);
    return () => window.clearInterval(poller);
  }, [phase, jobId, fetchOnce, job?.status]);

  const cancel = useCallback(async () => {
    setActionPending(true);
    setActionError(null);
    try {
      const updated = await apiClient<JobViewModel>(`/jobs/${encodeURIComponent(jobId)}/cancel`, {
        method: 'POST',
        headers: { ...mutationHeaders() },
        body: JSON.stringify({}),
      });
      setJob(updated);
      if (isTerminal(updated.status)) setPhase('done');
    } catch (err) {
      setActionError(jobProblemMessage(err));
    } finally {
      setActionPending(false);
    }
  }, [jobId]);

  const retry = useCallback(async () => {
    setActionPending(true);
    setActionError(null);
    try {
      const updated = await apiClient<JobViewModel>(`/jobs/${encodeURIComponent(jobId)}/retry`, {
        method: 'POST',
        headers: { ...mutationHeaders() },
        body: JSON.stringify({}),
      });
      setJob(updated);
      if (!isTerminal(updated.status) && phaseRef.current !== 'live') setPhase('polling');
      // Confirm authority right away so the UI never shows a stale terminal.
      try {
        const confirmed = await fetchOnce();
        if (confirmed && isTerminal(confirmed.status)) setPhase('done');
      } catch {
        // Polling continues and will converge.
      }
    } catch (err) {
      setActionError(jobProblemMessage(err));
    } finally {
      setActionPending(false);
    }
  }, [jobId, fetchOnce]);

  return {
    job,
    phase,
    reconnecting: phase === 'polling',
    error,
    refresh,
    cancel,
    retry,
    actionError,
    actionPending,
  };
}

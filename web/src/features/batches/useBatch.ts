/**
 * Batch aggregates (Task 7): create review state, authoritative detail reads,
 * and failed-item recovery that never re-submits successful children.
 *
 * Backend: POST /batches { mix_ids, max_parallelism } fans out one ANALYSIS
 * child per mix; GET /batches/:batchId returns derived counts. There is no
 * batch-level retry endpoint, so failed-item recovery retries each FAILED
 * child through POST /jobs/:jobId/retry individually.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { authHeaders } from '../../api';
import { apiClient, type ApiProblem } from '../../api/client';

export interface BatchItemView {
  job_id: string;
  mix_id: string;
  status: string;
}

export interface BatchAggregate {
  id: string;
  project_id: string;
  status: string;
  total_count: number;
  queued_count: number;
  running_count: number;
  completed_count: number;
  failed_count: number;
  cancelled_count: number;
  items: BatchItemView[];
  created_at: string;
}

export type BatchPhase = 'loading' | 'ready' | 'error';

const BATCH_TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED', 'PARTIAL_FAILED']);
const BATCH_POLL_MS = 5000;

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

export function batchProblemMessage(problem: unknown): string {
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

export function isBatchTerminal(status: string | undefined | null): boolean {
  return BATCH_TERMINAL.has((status || '').toUpperCase());
}

/** Fan out one ANALYSIS child per selected mix (bounded parallelism). */
export async function createBatch(
  mixIds: string[],
  maxParallelism: number,
): Promise<BatchAggregate> {
  return apiClient<BatchAggregate>('/batches', {
    method: 'POST',
    headers: { ...mutationHeaders() },
    body: JSON.stringify({ mix_ids: mixIds, max_parallelism: maxParallelism }),
  });
}

export interface UseBatchDetailResult {
  batch: BatchAggregate | null;
  phase: BatchPhase;
  error: string | null;
  notice: string | null;
  retryPending: boolean;
  failedIds: string[];
  refresh: () => void;
  retryFailed: () => void;
}

export function useBatchDetail(batchId: string): UseBatchDetailResult {
  const [batch, setBatch] = useState<BatchAggregate | null>(null);
  const [phase, setPhase] = useState<BatchPhase>('loading');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [retryPending, setRetryPending] = useState(false);
  const batchRef = useRef<BatchAggregate | null>(null);
  batchRef.current = batch;

  const fetchOnce = useCallback(async (): Promise<BatchAggregate> => {
    const fresh = await apiClient<BatchAggregate>(`/batches/${encodeURIComponent(batchId)}`, {
      headers: { ...mutationHeaders() },
    });
    setBatch(fresh);
    return fresh;
  }, [batchId]);

  const refresh = useCallback(() => {
    setError(null);
    void fetchOnce()
      .then(() => setPhase('ready'))
      .catch((err: unknown) => {
        setError(batchProblemMessage(err));
        setPhase((prev) => (batchRef.current ? prev : 'error'));
      });
  }, [fetchOnce]);

  useEffect(() => {
    let cancelled = false;
    setPhase('loading');
    setError(null);
    void fetchOnce()
      .then(() => {
        if (!cancelled) setPhase('ready');
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(batchProblemMessage(err));
          setPhase('error');
        }
      });
    const poller = window.setInterval(() => {
      const current = batchRef.current;
      if (current && isBatchTerminal(current.status)) return;
      void fetchOnce().catch(() => {
        // Keep last authoritative aggregate on transient failures.
      });
    }, BATCH_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(poller);
    };
  }, [batchId, fetchOnce]);

  const retryFailed = useCallback(() => {
    const current = batchRef.current;
    if (!current) return;
    const failedIds = (current.items || [])
      .filter((item) => (item.status || '').toUpperCase() === 'FAILED')
      .map((item) => item.job_id);
    if (failedIds.length === 0) return;
    setRetryPending(true);
    setNotice(null);
    setError(null);
    void (async () => {
      let ok = 0;
      let bad = 0;
      for (const jobId of failedIds) {
        try {
          await apiClient<unknown>(`/jobs/${encodeURIComponent(jobId)}/retry`, {
            method: 'POST',
            headers: { ...mutationHeaders() },
            body: JSON.stringify({}),
          });
          ok += 1;
        } catch {
          bad += 1;
        }
      }
      try {
        await fetchOnce();
      } catch (err) {
        setError(batchProblemMessage(err));
      }
      if (bad === 0) {
        setNotice(`Re-queued ${ok} failed item${ok === 1 ? '' : 's'}. Completed items were left untouched.`);
      } else {
        setNotice(`Re-queued ${ok} of ${failedIds.length} failed items; ${bad} could not be retried.`);
      }
      setRetryPending(false);
    })();
  }, [fetchOnce]);

  const failedIds = (batch?.items || [])
    .filter((item) => (item.status || '').toUpperCase() === 'FAILED')
    .map((item) => item.job_id);

  return { batch, phase, error, notice, retryPending, failedIds, refresh, retryFailed };
}

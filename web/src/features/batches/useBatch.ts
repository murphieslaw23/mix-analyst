import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, asApiProblem, type ApiProblem } from "../../api/client";
import { asBatchDto, isBatchTerminal, toBatchViewModel, type BatchViewModel } from "./batchAdapters";

type BatchResource =
  | { status: "loading"; batch: null; problem: null }
  | { status: "ready"; batch: BatchViewModel; problem: null }
  | { status: "error"; batch: null; problem: ApiProblem };

const POLL_INTERVAL_MS = 5_000;

/** Reads the server-owned aggregate and retries only explicitly failed children. */
export function useBatch(batchId: string | undefined) {
  const [resource, setResource] = useState<BatchResource>({ status: "loading", batch: null, problem: null });
  const [actionPending, setActionPending] = useState(false);
  const [actionProblem, setActionProblem] = useState<ApiProblem | null>(null);
  const mounted = useRef(false);
  const requestVersion = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    if (!batchId) {
      setResource({ status: "error", batch: null, problem: { status: 404, title: "Batch unavailable", detail: "This batch address is incomplete.", retryable: false } });
      return;
    }
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const version = ++requestVersion.current;
    setResource((current) => current.status === "ready" ? current : { status: "loading", batch: null, problem: null });
    void (async () => {
      try {
        const response = await apiClient<unknown>(`/batches/${encodeURIComponent(batchId)}`, { signal: controller.signal });
        const batch = toBatchViewModel(asBatchDto(response));
        if (!controller.signal.aborted && mounted.current && version === requestVersion.current) {
          setResource({ status: "ready", batch, problem: null });
        }
      } catch (error) {
        if (!controller.signal.aborted && mounted.current && version === requestVersion.current) {
          setResource({ status: "error", batch: null, problem: asApiProblem(error) });
        }
      }
    })();
  }, [batchId]);

  useEffect(() => {
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
      activeRequest.current?.abort();
    };
  }, [load]);

  useEffect(() => {
    if (resource.status !== "ready" || isBatchTerminal(resource.batch.status)) return;
    const interval = window.setInterval(load, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [load, resource]);

  const retryFailed = useCallback(async (jobIds: string[]) => {
    if (!batchId || jobIds.length === 0 || actionPending) return;
    setActionPending(true);
    setActionProblem(null);
    try {
      const response = await apiClient<unknown>(`/batches/${encodeURIComponent(batchId)}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: jobIds }),
      });
      const batch = toBatchViewModel(asBatchDto(response));
      if (mounted.current) setResource({ status: "ready", batch, problem: null });
    } catch (error) {
      if (mounted.current) setActionProblem(asApiProblem(error));
    } finally {
      if (mounted.current) setActionPending(false);
    }
  }, [actionPending, batchId]);

  return { ...resource, actionPending, actionProblem, retryFailed, retryLoad: load };
}

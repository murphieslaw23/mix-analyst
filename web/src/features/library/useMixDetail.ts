import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, asApiProblem, type ApiProblem } from "../../api/client";
import { asMixDto, toMixDetail, type MixDetail } from "../../api/mixAdapters";

type MixDetailResource =
  | { status: "loading"; mix: null; problem: null }
  | { status: "ready"; mix: MixDetail; problem: null }
  | { status: "error"; mix: null; problem: ApiProblem };

const loading: MixDetailResource = { status: "loading", mix: null, problem: null };

export function useMixDetail(mixId: string | undefined) {
  const [resource, setResource] = useState<MixDetailResource>(loading);
  const requestRef = useRef<AbortController | null>(null);
  const versionRef = useRef(0);

  const load = useCallback(() => {
    requestRef.current?.abort();
    if (!mixId) {
      setResource({ status: "error", mix: null, problem: { status: 404, title: "Mix not found", detail: "This result does not have a valid address.", retryable: false } });
      return;
    }
    const controller = new AbortController();
    requestRef.current = controller;
    const version = ++versionRef.current;
    setResource(loading);
    void (async () => {
      try {
        const result = await apiClient<unknown>(`/mixes/${encodeURIComponent(mixId)}`, { signal: controller.signal });
        if (!controller.signal.aborted && version === versionRef.current) setResource({ status: "ready", mix: toMixDetail(asMixDto(result)), problem: null });
      } catch (error) {
        if (!controller.signal.aborted && version === versionRef.current) setResource({ status: "error", mix: null, problem: asApiProblem(error) });
      }
    })();
  }, [mixId]);

  useEffect(() => {
    load();
    return () => requestRef.current?.abort();
  }, [load]);

  return { ...resource, retry: load };
}

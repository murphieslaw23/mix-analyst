import { useCallback, useEffect, useState } from "react";
import { apiClient, asApiProblem, type ApiProblem } from "../../api/client";
import { asMixListDto, toLibraryMixSummaries, type LibraryMixSummary } from "../../api/mixAdapters";
import type { MixListDto } from "../../api/contracts";

type LibraryResource =
  | { status: "loading"; mixes: LibraryMixSummary[]; total: number; problem: null }
  | { status: "ready"; mixes: LibraryMixSummary[]; total: number; problem: null }
  | { status: "error"; mixes: LibraryMixSummary[]; total: number; problem: ApiProblem };

const loadingState: LibraryResource = { status: "loading", mixes: [], total: 0, problem: null };

export function useLibraryMixes() {
  const [resource, setResource] = useState<LibraryResource>(loadingState);

  const load = useCallback(async (signal?: AbortSignal) => {
    setResource(loadingState);
    try {
      const response = await apiClient<unknown>("/mixes", { signal });
      const list: MixListDto = asMixListDto(response);
      if (!signal?.aborted) {
        setResource({ status: "ready", mixes: toLibraryMixSummaries(list), total: list.total, problem: null });
      }
    } catch (error) {
      if (!signal?.aborted) {
        setResource({ status: "error", mixes: [], total: 0, problem: asApiProblem(error) });
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  return { ...resource, retry: load };
}

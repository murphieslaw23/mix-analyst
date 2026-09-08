import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, asApiProblem, type ApiProblem } from "../../api/client";
import { asMixListDto, toLibraryMixSummaries, type LibraryMixSummary } from "../../api/mixAdapters";
import type { MixListDto } from "../../api/contracts";

type LibraryResource =
  | { status: "loading"; mixes: LibraryMixSummary[]; total: number; unmasteredMixCount: number; problem: null }
  | { status: "ready"; mixes: LibraryMixSummary[]; total: number; unmasteredMixCount: number; problem: null }
  | { status: "error"; mixes: LibraryMixSummary[]; total: number; unmasteredMixCount: number; problem: ApiProblem };

const loadingState: LibraryResource = { status: "loading", mixes: [], total: 0, unmasteredMixCount: 0, problem: null };

export function useLibraryMixes() {
  const [resource, setResource] = useState<LibraryResource>(loadingState);
  const isMounted = useRef(false);
  const activeRequest = useRef<AbortController | null>(null);
  const requestVersion = useRef(0);

  const load = useCallback(() => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const version = ++requestVersion.current;

    setResource(loadingState);
    void (async () => {
      try {
        const response = await apiClient<unknown>("/mixes", { signal: controller.signal });
        const list: MixListDto = asMixListDto(response);
        const mixes = toLibraryMixSummaries(list);
        if (!controller.signal.aborted && isMounted.current && version === requestVersion.current) {
          setResource({
            status: "ready",
            mixes,
            total: mixes.length,
            unmasteredMixCount: list.items.length - mixes.length,
            problem: null,
          });
        }
      } catch (error) {
        if (!controller.signal.aborted && isMounted.current && version === requestVersion.current) {
          setResource({ status: "error", mixes: [], total: 0, unmasteredMixCount: 0, problem: asApiProblem(error) });
        }
      }
    })();
  }, []);

  useEffect(() => {
    isMounted.current = true;
    load();
    return () => {
      isMounted.current = false;
      activeRequest.current?.abort();
    };
  }, [load]);

  const retry = useCallback(() => {
    load();
  }, [load]);

  return { ...resource, retry };
}

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient, asApiProblem, type ApiProblem } from "../../api/client";
import type { BatchDto, MixListDto } from "../../api/contracts";
import { asMixListDto } from "../../api/mixAdapters";
import { BATCHES_ROUTE, PROCESS_ROUTE } from "../../app/routes";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { LiveRegion } from "../../components/ui/LiveRegion";
import { Skeleton } from "../../components/ui/Skeleton";
import { presetOptions, type MasteringPresetId } from "../process/types";
import { asBatchDto } from "./batchAdapters";

type MixResource =
  | { status: "loading"; mixes: MixListDto["items"]; problem: null }
  | { status: "ready"; mixes: MixListDto["items"]; problem: null }
  | { status: "error"; mixes: MixListDto["items"]; problem: ApiProblem };

const loadingState: MixResource = { status: "loading", mixes: [], problem: null };

/** Select existing server-confirmed mixes before issuing one durable batch command. */
export function BatchReviewPage() {
  const navigate = useNavigate();
  const [resource, setResource] = useState<MixResource>(loadingState);
  const [selectedMixIds, setSelectedMixIds] = useState<Set<string>>(() => new Set());
  const [presetId, setPresetId] = useState<MasteringPresetId>("sound_system_heavy");
  const [maxParallelism, setMaxParallelism] = useState(1);
  const [creating, setCreating] = useState(false);
  const [createProblem, setCreateProblem] = useState<ApiProblem | null>(null);
  const mounted = useRef(false);
  const activeRequest = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setResource(loadingState);
    void (async () => {
      try {
        const response = await apiClient<unknown>("/mixes", { signal: controller.signal });
        const mixes = asMixListDto(response).items;
        if (!controller.signal.aborted && mounted.current) {
          setResource({ status: "ready", mixes, problem: null });
          // A refresh can never leave stale, hidden ids selected for submission.
          setSelectedMixIds((current) => new Set([...current].filter((id) => mixes.some((mix) => mix.id === id))));
        }
      } catch (error) {
        if (!controller.signal.aborted && mounted.current) setResource({ status: "error", mixes: [], problem: asApiProblem(error) });
      }
    })();
  }, []);

  useEffect(() => {
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
      activeRequest.current?.abort();
    };
  }, [load]);

  const toggle = (mixId: string) => {
    setSelectedMixIds((current) => {
      const next = new Set(current);
      if (next.has(mixId)) next.delete(mixId); else next.add(mixId);
      return next;
    });
  };

  const createBatch = () => {
    if (resource.status !== "ready" || selectedMixIds.size === 0 || creating) return;
    const mixIds = resource.mixes.filter((mix) => selectedMixIds.has(mix.id)).map((mix) => mix.id);
    setCreating(true);
    setCreateProblem(null);
    void (async () => {
      try {
        const response = await apiClient<unknown>("/batches", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mix_ids: mixIds, preset: { preset_id: presetId }, max_parallelism: maxParallelism }),
        });
        const batch: BatchDto = asBatchDto(response);
        if (mounted.current) navigate(`${BATCHES_ROUTE}/${encodeURIComponent(batch.id)}`);
      } catch (error) {
        if (mounted.current) setCreateProblem(asApiProblem(error));
      } finally {
        if (mounted.current) setCreating(false);
      }
    })();
  };

  const selectedCount = selectedMixIds.size;
  return (
    <section className="route-page batch-review-page" aria-labelledby="page-heading">
      <p className="eyebrow">Press plate intake · batch</p>
      <h1 id="page-heading" tabIndex={-1}>Review batch</h1>
      <p className="route-page__description">Choose saved audio already in this project. The service creates one durable mastering job for each checked item.</p>
      <Link className="back-link" to={PROCESS_ROUTE}>Process one audio file</Link>

      {resource.status === "loading" ? <Skeleton label="Loading saved audio" /> : null}
      {resource.status === "error" && resource.problem ? <ErrorState problem={resource.problem} onRetry={load} /> : null}
      {resource.status === "ready" && resource.mixes.length === 0 ? <EmptyState title="No saved audio to batch">Process audio first. It will appear here only after the service has saved it.</EmptyState> : null}
      {resource.status === "ready" && resource.mixes.length > 0 ? (
        <form className="batch-review" onSubmit={(event) => { event.preventDefault(); createBatch(); }}>
          <p className="batch-review__count" aria-live="polite"><strong>{selectedCount}</strong> selected of {resource.mixes.length} available audio item{resource.mixes.length === 1 ? "" : "s"}.</p>
          <fieldset className="batch-review__field">
            <legend>Audio to process</legend>
            <ol className="batch-review__items">
              {resource.mixes.map((mix) => (
                <li key={mix.id}>
                  <label className="batch-review__item">
                    <input aria-label={mix.media_asset.original_filename} checked={selectedMixIds.has(mix.id)} onChange={() => toggle(mix.id)} type="checkbox" />
                    <span><strong>{mix.title}</strong><small>{mix.media_asset.original_filename}</small></span>
                  </label>
                </li>
              ))}
            </ol>
          </fieldset>
          <fieldset className="batch-review__field">
            <legend>Batch settings</legend>
            <label htmlFor="batch-preset">Mastering preset</label>
            <select id="batch-preset" value={presetId} onChange={(event) => setPresetId(event.target.value as MasteringPresetId)}>
              {presetOptions.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}
            </select>
            <p>{presetOptions.find((preset) => preset.id === presetId)?.description}</p>
            <label htmlFor="batch-parallelism">Concurrent jobs</label>
            <select id="batch-parallelism" value={maxParallelism} onChange={(event) => setMaxParallelism(Number(event.target.value))}>
              {[1, 2, 3, 4].map((value) => <option key={value} value={value}>{value} at a time</option>)}
            </select>
            <p>Choose a bound from 1 to 4. The service enforces this limit while the batch runs.</p>
          </fieldset>
          {createProblem ? <ErrorState problem={createProblem} /> : null}
          <Button disabled={selectedCount === 0 || creating} type="submit">{creating ? "Creating batch" : "Create batch"}</Button>
          <LiveRegion>{creating ? "Creating durable batch jobs." : ""}</LiveRegion>
        </form>
      ) : null}
    </section>
  );
}

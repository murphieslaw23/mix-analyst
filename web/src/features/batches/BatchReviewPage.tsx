import React, { useCallback, useEffect, useState } from 'react';
import { authHeaders } from '../../api';
import { apiClient } from '../../api/client';
import { normalizeMixListResponse } from '../../api/contracts';
import { normalizeMixListItem } from '../../api/mixAdapters';
import { JOBS_ROUTE, PROCESS_ROUTE, batchDetailPath, navigate } from '../../app/routes';
import type { MixListItem } from '../../types';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LiveRegion } from '../../components/ui/LiveRegion';
import { Skeleton } from '../../components/ui/Skeleton';
import { batchProblemMessage, createBatch } from './useBatch';

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

interface BatchReviewPageProps {
  isDark?: boolean;
}

/**
 * Batch review (Task 7): stacked mobile checkbox list of owned mixes,
 * maxParallelism control, and one Create batch action. Selection alone
 * determines the submitted mix ids.
 */
export const BatchReviewPage: React.FC<BatchReviewPageProps> = ({ isDark = true }) => {
  const [mixes, setMixes] = useState<MixListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedMixIds, setSelectedMixIds] = useState<Set<string>>(new Set());
  const [maxParallelism, setMaxParallelism] = useState(2);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [liveMessage, setLiveMessage] = useState('Batch review loaded.');

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const btnPrimary =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded shadow-sm disabled:opacity-50 no-underline';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded no-underline'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded no-underline';
  const input = isDark
    ? 'bg-[#0d0e12] border-[#292c38] text-neutral-200'
    : 'bg-[#f9fafb] border-[#d1d5db] text-neutral-800';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const row = isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]';

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const raw: unknown = await apiClient<unknown>('/mixes', { headers: { ...mutationHeaders() } });
      const page = normalizeMixListResponse(raw);
      const items = page.items.map(normalizeMixListItem);
      setMixes(items);
      setLiveMessage(`Batch review loaded. ${items.length} mixes available.`);
    } catch (err) {
      setLoadError(batchProblemMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = useCallback((id: string) => {
    setSelectedMixIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const clampParallelism = (value: number): number => {
    if (Number.isNaN(value)) return 2;
    return Math.max(1, Math.min(8, Math.floor(value)));
  };

  const submit = useCallback(() => {
    const mixIds = mixes.filter((m) => selectedMixIds.has(m.id)).map((m) => m.id);
    if (mixIds.length === 0 || creating) return;
    setCreating(true);
    setCreateError(null);
    void createBatch(mixIds, clampParallelism(maxParallelism))
      .then((batch) => navigate(batchDetailPath(batch.id)))
      .catch((err: unknown) => {
        setCreateError(batchProblemMessage(err));
        setCreating(false);
      });
  }, [mixes, selectedMixIds, maxParallelism, creating]);

  const linkTo = (path: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };

  return (
    <div className="space-y-6" data-testid="batch-review-view">
      <LiveRegion message={liveMessage} />
      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide">Batch review</h2>
        <p className={`text-sm leading-relaxed mt-1 ${muted}`}>
          Select owned mixes to fan out one analysis job each. Only selected mixes
          are submitted.
        </p>
        <div className="flex flex-wrap gap-2 mt-4">
          <a href={JOBS_ROUTE} onClick={linkTo(JOBS_ROUTE)} className={btnGhost}>
            Back to Jobs
          </a>
          <a href={PROCESS_ROUTE} onClick={linkTo(PROCESS_ROUTE)} className={btnGhost}>
            Go to Pipeline &amp; Broadcast
          </a>
        </div>
      </div>

      <div className={`border rounded-lg p-5 ${card}`}>
        {loading && <Skeleton lines={3} label="Loading mixes" isDark={isDark} />}
        {!loading && loadError && (
          <ErrorState
            title="Could not load mixes"
            message={loadError}
            onRetry={() => void load()}
            retryLabel="Retry"
            isDark={isDark}
          />
        )}
        {!loading && !loadError && mixes.length === 0 && (
          <EmptyState
            title="No mixes yet."
            description="Upload a long set from Pipeline & Broadcast before creating a batch."
          />
        )}
        {!loading && !loadError && mixes.length > 0 && (
          <div className="space-y-4">
            <p className={`text-xs font-mono ${muted}`} data-testid="batch-selection-count" role="status">
              Selected {selectedMixIds.size} of {mixes.length}
            </p>
            {/* Stacked list on purpose: never a fixed-width desktop table. */}
            <ul className="flex flex-col gap-2" aria-label="Owned mixes">
              {mixes.map((mix) => {
                const label = mix.title || mix.original_filename;
                const checked = selectedMixIds.has(mix.id);
                return (
                  <li key={mix.id} className={`p-3 rounded border ${row}`}>
                    <label className="flex items-start gap-3 min-h-[44px] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(mix.id)}
                        aria-label={label}
                        data-testid={`batch-select-${mix.id}`}
                        className="mt-1 h-5 w-5 min-h-[20px] min-w-[20px] accent-[#ea580c]"
                      />
                      <span className="min-w-0">
                        <span className={`block text-sm font-semibold truncate ${isDark ? 'text-white' : 'text-gray-900'}`}>
                          {label}
                        </span>
                        <span className={`block text-[11px] font-mono ${muted}`}>
                          {mix.original_filename}
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
            <div className="flex flex-col sm:flex-row sm:items-end gap-3">
              <label className="block sm:w-48">
                <span className={`block text-xs font-semibold mb-1 ${muted}`}>Max parallelism (1–8)</span>
                <input
                  type="number"
                  min={1}
                  max={8}
                  value={maxParallelism}
                  onChange={(e) => setMaxParallelism(clampParallelism(Number(e.target.value)))}
                  aria-label="Max parallelism"
                  data-testid="batch-parallelism"
                  className={`w-full px-2.5 py-2 min-h-[44px] rounded border text-xs ${input}`}
                />
              </label>
              <button
                onClick={submit}
                disabled={selectedMixIds.size === 0 || creating}
                className={btnPrimary}
                data-testid="batch-create"
              >
                {creating ? 'Creating batch…' : `Create batch${selectedMixIds.size > 0 ? ` (${selectedMixIds.size})` : ''}`}
              </button>
            </div>
            {selectedMixIds.size === 0 && (
              <p className={`text-xs ${muted}`}>Select at least one mix to create a batch.</p>
            )}
            {createError && (
              <div role="alert" className="text-xs text-red-400">
                {createError}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default BatchReviewPage;

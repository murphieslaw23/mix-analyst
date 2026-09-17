import React, { useCallback, useEffect, useState } from 'react';
import { authHeaders } from '../../api';
import { apiClient } from '../../api/client';
import { normalizeMixListResponse } from '../../api/contracts';
import { normalizeMixListItem } from '../../api/mixAdapters';
import { JOBS_ROUTE, navigate, pipelinePath, useQueryParam } from '../../app/routes';
import type { MixListItem } from '../../types';
import { PipelinePanel } from '../../components/PipelinePanel';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LiveRegion } from '../../components/ui/LiveRegion';
import { Skeleton } from '../../components/ui/Skeleton';
import { jobProblemMessage } from '../jobs/useJobEvents';

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

interface PipelinePageProps {
  isDark?: boolean;
}

/**
 * Pipeline & Broadcast route (`/pipeline`, target mix in `?mix=`).
 *
 * Previously this surface depended on hidden selection state owned by the
 * `/` route, so direct visits rendered a dead "select a mix first" panel
 * with no way forward. Now the target mix is URL state with a picker
 * fallback (same convention as Jobs and Library).
 */
export const PipelinePage: React.FC<PipelinePageProps> = ({ isDark = true }) => {
  const mixParam = useQueryParam('mix');
  const [mixes, setMixes] = useState<MixListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [liveMessage, setLiveMessage] = useState('Pipeline view loaded.');

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded no-underline'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded no-underline';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const row = isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const raw: unknown = await apiClient<unknown>('/mixes', {
        headers: { ...mutationHeaders() },
      });
      const page = normalizeMixListResponse(raw);
      const items = page.items.map(normalizeMixListItem);
      setMixes(items);
      setLiveMessage(`Pipeline view loaded. ${items.length} mixes available.`);
    } catch (err) {
      setError(jobProblemMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const linkTo = (path: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };

  const target = mixParam ? mixes.find((m) => m.id === mixParam) ?? null : null;
  // A ?mix= id that is not (yet) in the list still renders the panel: job
  // endpoints are authoritative per mix and do not need the list entry.
  const effectiveMix = mixParam
    ? { id: mixParam, title: target?.title ?? target?.original_filename ?? mixParam }
    : null;

  return (
    <div className="space-y-6" data-testid="pipeline-view">
      <LiveRegion message={liveMessage} />
      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide">
          Pipeline &amp; Broadcast
        </h2>
        <p className={`text-sm leading-relaxed mt-1 ${muted}`}>
          {effectiveMix
            ? `Operations for ${effectiveMix.title}. Uploads start in Process audio; analysis jobs, mastering, stems and broadcast run here.`
            : 'Pick a mix to run pipeline operations, or start with a fresh upload.'}
        </p>
        <div className="flex flex-wrap gap-2 mt-4">
          <a href="/process" onClick={linkTo('/process')} className={btnGhost}>
            Go to Process audio
          </a>
          <a
            href={JOBS_ROUTE}
            onClick={linkTo(effectiveMix ? `${JOBS_ROUTE}?mix=${encodeURIComponent(effectiveMix.id)}` : JOBS_ROUTE)}
            className={btnGhost}
          >
            Open Jobs
          </a>
          {effectiveMix && (
            <a href="/pipeline" onClick={linkTo('/pipeline')} className={btnGhost}>
              Choose a different mix
            </a>
          )}
        </div>
      </div>

      {loading && (
        <div className={`border rounded-lg p-5 ${card}`}>
          <Skeleton lines={3} label="Loading mixes" isDark={isDark} />
        </div>
      )}

      {!loading && error && (
        <div className={`border rounded-lg p-5 ${card}`}>
          <ErrorState
            title="Could not load mixes"
            message={error}
            onRetry={() => void load()}
            retryLabel="Retry"
            isDark={isDark}
          />
        </div>
      )}

      {!loading && !error && !effectiveMix && (
        <div className={`border rounded-lg p-5 ${card}`}>
          <h3 className={`text-xs font-bold uppercase tracking-widest mb-3 ${muted}`}>Select a mix</h3>
          {mixes.length === 0 ? (
            <EmptyState
              title="No mixes yet."
              description="Upload a long set from Process audio to start pipeline operations."
            />
          ) : (
            <ul className="space-y-2">
              {mixes.map((mix) => (
                <li key={mix.id} className={`p-3 rounded border ${row}`}>
                  <a
                    href={pipelinePath(mix.id)}
                    onClick={linkTo(pipelinePath(mix.id))}
                    className={`block min-h-[44px] font-semibold text-sm ${isDark ? 'text-white' : 'text-gray-900'} hover:text-[#ea580c]`}
                  >
                    Open pipeline for {mix.title || mix.original_filename}
                  </a>
                  <p className={`text-[11px] font-mono mt-0.5 ${muted}`}>{mix.original_filename}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {!loading && !error && effectiveMix && (
        <PipelinePanel mix={effectiveMix} isDark={isDark} />
      )}
    </div>
  );
};

export default PipelinePage;

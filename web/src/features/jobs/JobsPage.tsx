import React, { useCallback, useEffect, useState } from 'react';
import { authHeaders } from '../../api';
import { apiClient } from '../../api/client';
import { normalizeMixListResponse } from '../../api/contracts';
import { normalizeMixListItem } from '../../api/mixAdapters';
import {
  BATCHES_ROUTE,
  PROCESS_ROUTE,
  jobDetailPath,
  navigate,
  pipelinePath,
  useQueryParam,
} from '../../app/routes';
import type { MixListItem } from '../../types';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LiveRegion } from '../../components/ui/LiveRegion';
import { Progress } from '../../components/ui/Progress';
import { Skeleton } from '../../components/ui/Skeleton';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { jobProblemMessage, type JobViewModel } from './useJobEvents';

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

type JobsViewState =
  | { kind: 'picking-mix'; mixes: MixListItem[]; loading: boolean; error: string | null }
  | { kind: 'listing'; mixId: string; mixLabel: string; jobs: JobViewModel[]; loading: boolean; error: string | null };

interface JobsPageProps {
  isDark?: boolean;
}

/**
 * Jobs list (Task 4). Needs a mix context: accepts ?mix=, otherwise offers a
 * mix picker from GET /mixes. The Pipeline & Broadcast link is always
 * rendered so dispatch stays discoverable (and the shell marker stable).
 */
export const JobsPage: React.FC<JobsPageProps> = ({ isDark = true }) => {
  const mixParam = useQueryParam('mix');
  const [state, setState] = useState<JobsViewState>({
    kind: mixParam ? 'listing' : 'picking-mix',
    ...(mixParam
      ? { mixId: mixParam, mixLabel: mixParam, jobs: [], loading: true, error: null }
      : { mixes: [], loading: true, error: null }),
  } as JobsViewState);
  const [liveMessage, setLiveMessage] = useState('Jobs view loaded.');

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const btnPrimary =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded shadow-sm disabled:opacity-50 no-underline';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded no-underline'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded no-underline';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const row = isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]';

  const loadMixes = useCallback(async () => {
    setState({ kind: 'picking-mix', mixes: [], loading: true, error: null });
    try {
      const raw: unknown = await apiClient<unknown>('/mixes', { headers: { ...mutationHeaders() } });
      const page = normalizeMixListResponse(raw);
      const mixes = page.items.map(normalizeMixListItem);
      setState({ kind: 'picking-mix', mixes, loading: false, error: null });
      setLiveMessage(`Jobs view loaded. ${mixes.length} mixes available.`);
    } catch (err) {
      setState({ kind: 'picking-mix', mixes: [], loading: false, error: jobProblemMessage(err) });
    }
  }, []);

  const loadJobs = useCallback(async (mixId: string) => {
    setState((prev) =>
      prev.kind === 'listing' && prev.mixId === mixId
        ? { ...prev, loading: true, error: null }
        : { kind: 'listing', mixId, mixLabel: mixId, jobs: [], loading: true, error: null },
    );
    try {
      const [jobs, detail] = await Promise.all([
        apiClient<JobViewModel[]>(`/mixes/${encodeURIComponent(mixId)}/jobs`, {
          headers: { ...mutationHeaders() },
        }),
        apiClient<{ title?: string; original_filename?: string }>(
          `/mixes/${encodeURIComponent(mixId)}`,
          { headers: { ...mutationHeaders() } },
        ).catch(() => null),
      ]);
      const list = Array.isArray(jobs) ? jobs : [];
      const label = detail?.title || (detail as { original_filename?: string } | null)?.original_filename || mixId;
      setState({ kind: 'listing', mixId, mixLabel: label, jobs: list, loading: false, error: null });
      setLiveMessage(`Jobs view loaded. ${list.length} jobs for ${label}.`);
    } catch (err) {
      setState((prev) =>
        prev.kind === 'listing'
          ? { ...prev, loading: false, error: jobProblemMessage(err) }
          : prev,
      );
    }
  }, []);

  useEffect(() => {
    if (mixParam) void loadJobs(mixParam);
    else void loadMixes();
  }, [mixParam, loadJobs, loadMixes]);

  const linkTo = (path: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };

  return (
    <div className="space-y-6" data-testid="jobs-view">
      <LiveRegion message={liveMessage} />
      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide">Jobs</h2>
        <p className={`text-sm leading-relaxed mt-1 ${muted}`}>
          {state.kind === 'listing'
            ? `Engine jobs for ${state.mixLabel}. Progress streams live; failed jobs keep their error and can be retried.`
            : 'Pick a mix to review its engine jobs, or open Pipeline & Broadcast to dispatch new ones.'}
        </p>
        <div className="flex flex-wrap gap-2 mt-4">
          <a
            href={state.kind === 'listing' ? pipelinePath(state.mixId) : PROCESS_ROUTE}
            onClick={linkTo(state.kind === 'listing' ? pipelinePath(state.mixId) : PROCESS_ROUTE)}
            className={btnPrimary}
          >
            Go to Pipeline &amp; Broadcast
          </a>
          <a href={BATCHES_ROUTE} onClick={linkTo(BATCHES_ROUTE)} className={btnGhost}>
            Review batches
          </a>
          {state.kind === 'listing' && (
            <a href="/jobs" onClick={linkTo('/jobs')} className={btnGhost}>
              Choose a different mix
            </a>
          )}
        </div>
      </div>

      {state.kind === 'picking-mix' && (
        <div className={`border rounded-lg p-5 ${card}`}>
          <h3 className={`text-xs font-bold uppercase tracking-widest mb-3 ${muted}`}>Select a mix</h3>
          {state.loading && <Skeleton lines={3} label="Loading mixes" isDark={isDark} />}
          {!state.loading && state.error && (
            <ErrorState
              title="Could not load mixes"
              message={state.error}
              onRetry={() => void loadMixes()}
              retryLabel="Retry"
              isDark={isDark}
            />
          )}
          {!state.loading && !state.error && state.mixes.length === 0 && (
            <EmptyState
              title="No mixes yet."
              description="Upload a long set from Pipeline & Broadcast to start engine analysis."
            />
          )}
          {!state.loading && !state.error && state.mixes.length > 0 && (
            <ul className="space-y-2">
              {state.mixes.map((mix) => (
                <li key={mix.id} className={`p-3 rounded border ${row}`}>
                  <a
                    href={`/jobs?mix=${encodeURIComponent(mix.id)}`}
                    onClick={linkTo(`/jobs?mix=${encodeURIComponent(mix.id)}`)}
                    className={`block min-h-[44px] font-semibold text-sm ${isDark ? 'text-white' : 'text-gray-900'} hover:text-[#ea580c]`}
                  >
                    Open jobs for {mix.title || mix.original_filename}
                  </a>
                  <p className={`text-[11px] font-mono mt-0.5 ${muted}`}>{mix.original_filename}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {state.kind === 'listing' && (
        <div className={`border rounded-lg p-5 ${card}`}>
          <h3 className={`text-xs font-bold uppercase tracking-widest mb-3 ${muted}`}>
            Jobs for {state.mixLabel}
          </h3>
          {state.loading && <Skeleton lines={3} label="Loading jobs" isDark={isDark} />}
          {!state.loading && state.error && (
            <ErrorState
              title="Could not load jobs"
              message={state.error}
              onRetry={() => void loadJobs(state.mixId)}
              retryLabel="Retry"
              isDark={isDark}
            />
          )}
          {!state.loading && !state.error && state.jobs.length === 0 && (
            <EmptyState
              title="No jobs dispatched for this mix yet."
              description="Dispatch analysis from Pipeline & Broadcast, then track it here."
            />
          )}
          {!state.loading && !state.error && state.jobs.length > 0 && (
            <ul className="space-y-2" data-testid="jobs-list">
              {state.jobs.map((job) => (
                <li
                  key={job.id}
                  className={`p-3 rounded border ${row}`}
                  data-testid="job-row"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <a
                      href={jobDetailPath(job.id)}
                      onClick={linkTo(jobDetailPath(job.id))}
                      className="font-mono font-bold text-sm text-[#ea580c] hover:underline min-h-[44px] inline-flex items-center"
                    >
                      {job.job_type}
                    </a>
                    <StatusBadge status={job.status} isDark={isDark} />
                    <span className={`font-mono text-[11px] ${muted}`}>
                      {(job.progress_percent || 0).toFixed(0)}% · {job.current_stage || '—'}
                    </span>
                  </div>
                  {typeof job.progress_percent === 'number' && (
                    <div className="mt-2">
                      <Progress
                        value={job.progress_percent}
                        label={`Progress for job ${job.id}`}
                        testId={`job-progress-${job.id}`}
                        isDark={isDark}
                      />
                    </div>
                  )}
                  {job.error_message && (
                    <p className="text-red-400 font-mono text-[11px] mt-1">{job.error_message}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default JobsPage;

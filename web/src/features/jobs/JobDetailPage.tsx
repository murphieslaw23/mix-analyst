import React, { useState } from 'react';
import { PROCESS_ROUTE, jobDetailPath, navigate } from '../../app/routes';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LiveRegion } from '../../components/ui/LiveRegion';
import { Progress } from '../../components/ui/Progress';
import { Skeleton } from '../../components/ui/Skeleton';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { useJobEvents } from './useJobEvents';

interface JobDetailPageProps {
  jobId: string;
  isDark?: boolean;
}

/**
 * Job detail (Task 4): SSE-first live progress with polling fallback,
 * cancel/retry recovery, and persistent terminal errors.
 */
export const JobDetailPage: React.FC<JobDetailPageProps> = ({ jobId, isDark = true }) => {
  const { job, phase, reconnecting, error, refresh, cancel, retry, actionError, actionPending } =
    useJobEvents(jobId);
  const [liveMessage, setLiveMessage] = useState(`Job ${jobId} loading.`);

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const btnPrimary =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded shadow-sm disabled:opacity-50 no-underline';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded disabled:opacity-50 no-underline'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded disabled:opacity-50 no-underline';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';

  const status = (job?.status || '').toUpperCase();
  const terminal = status === 'SUCCEEDED' || status === 'FAILED' || status === 'CANCELLED';
  const failed = status === 'FAILED';
  const retryable = failed || status === 'CANCELLED';

  const lastAnnouncement = React.useRef('');
  React.useEffect(() => {
    if (job) {
      const stage = job.current_stage ? ` Stage: ${job.current_stage}.` : '';
      const message =
        `Job ${job.id} ${job.status} at ${Math.round(job.progress_percent || 0)} percent.${stage}${
          reconnecting ? ' Live stream unavailable, polling for updates.' : ''
        }`;
      if (message !== lastAnnouncement.current) {
        lastAnnouncement.current = message;
        setLiveMessage(message);
      }
    } else if (phase === 'error') {
      setLiveMessage(`Job ${jobId} could not be loaded.`);
    }
  }, [jobId, job, reconnecting, phase]);

  const backHref = job?.mix_id ? `/jobs?mix=${encodeURIComponent(job.mix_id)}` : '/jobs';
  const linkTo = (path: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };

  return (
    <div className="space-y-6" data-testid="job-detail-view">
      <LiveRegion message={liveMessage} />
      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <p className={`text-[11px] font-mono ${muted}`} data-testid="job-detail-id">
          {jobDetailPath(jobId)}
        </p>
        <div className="flex flex-wrap items-center gap-3 mt-1">
          <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide">
            {job ? `${job.job_type} job` : 'Job detail'}
          </h2>
          {job && <StatusBadge status={job.status} isDark={isDark} />}
        </div>

        {phase === 'loading' && (
          <div className="mt-4">
            <Skeleton lines={3} label="Loading job" isDark={isDark} />
          </div>
        )}

        {phase === 'error' && !job && (
          <div className="mt-4">
            <ErrorState
              title="Could not load job"
              message={error ?? 'The job could not be loaded.'}
              onRetry={refresh}
              retryLabel="Retry"
              isDark={isDark}
            />
          </div>
        )}

        {job && (
          <div className="mt-4 space-y-3">
            {reconnecting && !terminal && (
              <p className={`text-xs ${muted}`} role="status">
                Live stream unavailable — polling for updates every few seconds.
              </p>
            )}
            <Progress
              value={job.progress_percent || 0}
              label={`Job progress for ${job.id}`}
              testId="job-detail-progress"
              isDark={isDark}
            />
            <p className={`text-xs font-mono ${muted}`} data-testid="job-detail-stage">
              Stage: {job.current_stage || '—'}
            </p>

            {failed && (
              <div role="alert" className="p-3 rounded border border-red-800 bg-red-950/40">
                <p className="font-semibold text-red-400 text-sm">Job failed</p>
                <p className="text-red-200 font-mono text-xs mt-1" data-testid="job-detail-error">
                  {job.error_message || 'The job failed without an error message.'}
                </p>
              </div>
            )}
            {status === 'CANCELLED' && (
              <p className={`text-xs ${muted}`} role="status">
                {job.error_message || 'This job was cancelled.'}
              </p>
            )}
            {status === 'SUCCEEDED' && (
              <p className="text-sm font-semibold text-emerald-400" role="status">
                Job completed successfully.
              </p>
            )}
            {!terminal && job.stage_runs && job.stage_runs.length > 0 && (
              <ul className="space-y-1" aria-label="Stage runs">
                {job.stage_runs.map((stage) => (
                  <li key={stage.id} className={`text-[11px] font-mono ${muted}`}>
                    {stage.stage_name}: {stage.status} {(stage.progress_percent || 0).toFixed(0)}%
                    {stage.error_message ? ` — ${stage.error_message}` : ''}
                  </li>
                ))}
              </ul>
            )}
            {actionError && (
              <p className="text-xs text-red-400" role="alert">
                {actionError}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              {!terminal && (
                <button
                  onClick={() => void cancel()}
                  disabled={actionPending}
                  className={btnGhost}
                  data-testid="job-detail-cancel"
                >
                  {actionPending ? 'Cancelling…' : 'Cancel job'}
                </button>
              )}
              {retryable && (
                <button
                  onClick={() => void retry()}
                  disabled={actionPending}
                  className={btnPrimary}
                  data-testid="job-detail-retry"
                >
                  {actionPending ? 'Retrying…' : 'Retry job'}
                </button>
              )}
              <a href={backHref} onClick={linkTo(backHref)} className={btnGhost}>
                Back to jobs
              </a>
              <a href={PROCESS_ROUTE} onClick={linkTo(PROCESS_ROUTE)} className={btnGhost}>
                Go to Pipeline &amp; Broadcast
              </a>
            </div>
          </div>
        )}

        {!job && phase !== 'loading' && phase !== 'error' && (
          <div className="mt-4">
            <EmptyState title="No job data yet." description="Retry to reload the job state." />
          </div>
        )}
      </div>
    </div>
  );
};

export default JobDetailPage;

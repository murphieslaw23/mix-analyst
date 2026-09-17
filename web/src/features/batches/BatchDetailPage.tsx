import React from 'react';
import { BATCHES_ROUTE, JOBS_ROUTE, jobDetailPath, navigate } from '../../app/routes';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LiveRegion } from '../../components/ui/LiveRegion';
import { Progress } from '../../components/ui/Progress';
import { Skeleton } from '../../components/ui/Skeleton';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { isBatchTerminal, useBatchDetail } from './useBatch';

interface BatchDetailPageProps {
  batchId: string;
  isDark?: boolean;
}

/** Batch aggregate detail (Task 7): authoritative counts, child states, retry. */
export const BatchDetailPage: React.FC<BatchDetailPageProps> = ({ batchId, isDark = true }) => {
  const { batch, phase, error, notice, retryPending, refresh, retryFailed } =
    useBatchDetail(batchId);

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const btnPrimary =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded shadow-sm disabled:opacity-50 no-underline';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded disabled:opacity-50 no-underline'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded disabled:opacity-50 no-underline';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const row = isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]';

  const liveMessage = batch
    ? `Batch ${batch.id} ${batch.status}. ${batch.completed_count} completed, ${batch.failed_count} failed of ${batch.total_count} total.`
    : phase === 'error'
      ? 'Batch could not be loaded.'
      : 'Batch detail loading.';

  const linkTo = (path: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };

  const total = batch?.total_count ?? 0;
  const doneShare = total > 0 ? ((batch?.completed_count ?? 0) / total) * 100 : 0;

  return (
    <div className="space-y-6" data-testid="batch-detail-view">
      <LiveRegion message={liveMessage} />
      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <p className={`text-[11px] font-mono ${muted}`} data-testid="batch-detail-id">
          /batches/{batchId}
        </p>
        <div className="flex flex-wrap items-center gap-3 mt-1">
          <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide">Batch detail</h2>
          {batch && <StatusBadge status={batch.status} isDark={isDark} />}
        </div>

        {phase === 'loading' && (
          <div className="mt-4">
            <Skeleton lines={3} label="Loading batch" isDark={isDark} />
          </div>
        )}
        {phase === 'error' && !batch && (
          <div className="mt-4">
            <ErrorState
              title="Could not load batch"
              message={error ?? 'The batch could not be loaded.'}
              onRetry={refresh}
              retryLabel="Retry"
              isDark={isDark}
            />
          </div>
        )}

        {batch && (
          <div className="mt-4 space-y-4">
            <p className={`text-sm font-mono ${muted}`} data-testid="batch-counts">
              {batch.completed_count} completed · {batch.failed_count} failed ·{' '}
              {batch.running_count} running · {batch.queued_count} queued ·{' '}
              {batch.cancelled_count} cancelled of {batch.total_count} total
            </p>
            <Progress
              value={doneShare}
              label={`Batch progress for ${batch.id}`}
              testId="batch-progress"
              isDark={isDark}
            />
            {batch.failed_count > 0 && (
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={retryFailed}
                  disabled={retryPending}
                  className={btnPrimary}
                  data-testid="batch-retry-failed"
                >
                  {retryPending
                    ? 'Retrying failed items…'
                    : `Retry failed items (${batch.failed_count})`}
                </button>
              </div>
            )}
            {notice && (
              <p className="text-xs text-emerald-400" role="status">
                {notice}
              </p>
            )}
            {error && (
              <p className="text-xs text-red-400" role="alert">
                {error}
              </p>
            )}
            {(batch.items || []).length === 0 ? (
              <EmptyState title="No batch items yet." description="Child jobs appear here once fanned out." />
            ) : (
              <ul className="flex flex-col gap-2" aria-label="Batch items" data-testid="batch-items">
                {batch.items.map((item) => (
                  <li
                    key={item.job_id}
                    className={`p-3 rounded border ${row}`}
                    data-testid="batch-item-row"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <a
                        href={jobDetailPath(item.job_id)}
                        onClick={linkTo(jobDetailPath(item.job_id))}
                        className="font-mono text-xs text-[#ea580c] hover:underline min-h-[44px] inline-flex items-center"
                      >
                        {item.job_id}
                      </a>
                      <StatusBadge status={item.status} isDark={isDark} />
                    </div>
                    <p className={`text-[11px] font-mono mt-1 ${muted}`}>mix {item.mix_id}</p>
                  </li>
                ))}
              </ul>
            )}
            {!isBatchTerminal(batch.status) && (
              <p className={`text-xs ${muted}`} role="status">
                Aggregate refreshes automatically while items are queued or running.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <a href={BATCHES_ROUTE} onClick={linkTo(BATCHES_ROUTE)} className={btnGhost}>
                Back to Batch review
              </a>
              <a href={JOBS_ROUTE} onClick={linkTo(JOBS_ROUTE)} className={btnGhost}>
                Back to Jobs
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BatchDetailPage;

import React from 'react';
import { formatTime } from '../../audio/format';
import {
  BATCHES_ROUTE,
  JOBS_ROUTE,
  LIBRARY_ROUTE,
  NOTIFICATIONS_ROUTE,
  PROCESS_INTAKE_ROUTE,
  PROCESS_ROUTE,
  jobDetailPath,
  libraryPath,
  navigate,
  pipelinePath,
} from '../../app/routes';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LiveRegion } from '../../components/ui/LiveRegion';
import { Skeleton } from '../../components/ui/Skeleton';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { safeNotificationLink } from '../notifications/notificationLinks';
import { useDashboard } from './useDashboard';

interface DashboardPageProps {
  isDark?: boolean;
}

/**
 * Start page: engine status at a glance, one-tap quick actions, recent
 * sets, and items needing attention. Heavy detail (waveform, ops) lives
 * behind deep links — the dashboard only issues cheap aggregate reads.
 */
export const DashboardPage: React.FC<DashboardPageProps> = ({ isDark = true }) => {
  const {
    phase,
    error,
    mixes,
    mixesTotal,
    activeJobs,
    failedJobs,
    unreadNotifications,
    unreadCount,
    liveMessage,
    refresh,
  } = useDashboard();

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const btnPrimary =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded shadow-sm no-underline';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded no-underline'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded no-underline';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const row = isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]';

  const linkTo = (path: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };

  const recentMixes = mixes.slice(0, 5);
  const firstMixId = mixes[0]?.id ?? null;
  const attentionCount = failedJobs.length + unreadCount;

  return (
    <div className="space-y-6" data-testid="dashboard-view">
      <LiveRegion message={liveMessage} />

      {/* Engine status + quick actions */}
      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <p className={`text-[11px] font-mono uppercase tracking-widest ${muted}`}>System Corrupt · engine room</p>
        <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide mt-1">
          Engine status
        </h2>
        {phase === 'loading' && (
          <div className="mt-4">
            <Skeleton lines={2} label="Loading engine status" isDark={isDark} />
          </div>
        )}
        {phase === 'error' && (
          <div className="mt-4">
            <ErrorState
              title="Could not load engine status"
              message={error ?? 'The dashboard could not be loaded.'}
              onRetry={refresh}
              retryLabel="Retry"
              isDark={isDark}
            />
          </div>
        )}
        {phase === 'ready' && (
          <>
            <p className={`text-sm leading-relaxed mt-1 ${muted}`} data-testid="dashboard-summary" role="status">
              {mixesTotal === 0
                ? 'No sets in the archive yet. Upload a long set to start engine analysis.'
                : `${mixesTotal} ${mixesTotal === 1 ? 'set' : 'sets'} in the archive · ${activeJobs.length} active ${activeJobs.length === 1 ? 'job' : 'jobs'} · ${failedJobs.length} failed · ${unreadCount} unread ${unreadCount === 1 ? 'notification' : 'notifications'}.`}
            </p>
            <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-2" aria-label="Engine status">
              <a href={LIBRARY_ROUTE} onClick={linkTo(LIBRARY_ROUTE)} className={`p-3 rounded border ${row} no-underline min-h-[44px]`}>
                <span className={`block text-[10px] font-bold uppercase tracking-widest ${muted}`}>Sets</span>
                <span className={`block mt-1 text-xl font-bold font-mono ${isDark ? 'text-white' : 'text-gray-900'}`} data-testid="dashboard-sets-count">
                  {mixesTotal}
                </span>
              </a>
              <a href={JOBS_ROUTE} onClick={linkTo(JOBS_ROUTE)} className={`p-3 rounded border ${row} no-underline min-h-[44px]`}>
                <span className={`block text-[10px] font-bold uppercase tracking-widest ${muted}`}>Active jobs</span>
                <span className={`block mt-1 text-xl font-bold font-mono ${isDark ? 'text-white' : 'text-gray-900'}`} data-testid="dashboard-active-count">
                  {activeJobs.length}
                </span>
              </a>
              <a href={JOBS_ROUTE} onClick={linkTo(JOBS_ROUTE)} className={`p-3 rounded border ${row} no-underline min-h-[44px]`}>
                <span className={`block text-[10px] font-bold uppercase tracking-widest ${muted}`}>Failed jobs</span>
                <span className="block mt-1 text-xl font-bold font-mono text-red-400" data-testid="dashboard-failed-count">
                  {failedJobs.length}
                </span>
              </a>
              <a href={NOTIFICATIONS_ROUTE} onClick={linkTo(NOTIFICATIONS_ROUTE)} className={`p-3 rounded border ${row} no-underline min-h-[44px]`}>
                <span className={`block text-[10px] font-bold uppercase tracking-widest ${muted}`}>Unread</span>
                <span className="block mt-1 text-xl font-bold font-mono text-[#ea580c]" data-testid="dashboard-unread-count">
                  {unreadCount}
                </span>
              </a>
            </div>
          </>
        )}
        <div className="flex flex-wrap gap-2 mt-4" aria-label="Quick actions">
          <a href={PROCESS_INTAKE_ROUTE} onClick={linkTo(PROCESS_INTAKE_ROUTE)} className={btnPrimary}>
            Process audio
          </a>
          <a href={LIBRARY_ROUTE} onClick={linkTo(LIBRARY_ROUTE)} className={btnGhost}>
            Open library
          </a>
          <a href={firstMixId ? pipelinePath(firstMixId) : PROCESS_ROUTE} onClick={linkTo(firstMixId ? pipelinePath(firstMixId) : PROCESS_ROUTE)} className={btnGhost}>
            Pipeline &amp; Broadcast
          </a>
          <a href={BATCHES_ROUTE} onClick={linkTo(BATCHES_ROUTE)} className={btnGhost}>
            Review batches
          </a>
        </div>
      </div>

      {phase === 'ready' && mixesTotal === 0 && (
        <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
          <h3 className={`text-xs font-bold uppercase tracking-widest mb-3 ${muted}`}>
            Getting started
          </h3>
          <ol className="space-y-2 list-none">
            {[
              { step: '1', title: 'Upload a long set', body: 'Resumable 5 MB chunks with ffprobe validation.', href: PROCESS_INTAKE_ROUTE, cta: 'Go to Process audio' },
              { step: '2', title: 'Dispatch engine analysis', body: 'Tempo, key, loudness, transitions and cue sheets.', href: PROCESS_ROUTE, cta: 'Go to Pipeline' },
              { step: '3', title: 'Inspect the result', body: 'Waveform, blend zones, A/B master and DJ exports.', href: LIBRARY_ROUTE, cta: 'Open library' },
            ].map((item) => (
              <li key={item.step} className={`p-3 rounded border ${row} flex flex-col sm:flex-row sm:items-center gap-2`}>
                <span className="flex items-start gap-3 min-w-0 flex-1">
                  <span className="w-6 h-6 rounded bg-[#ea580c] text-white text-xs font-black flex items-center justify-center shrink-0" aria-hidden="true">
                    {item.step}
                  </span>
                  <span className="min-w-0">
                    <span className={`block text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{item.title}</span>
                    <span className={`block text-xs ${muted}`}>{item.body}</span>
                  </span>
                </span>
                <a href={item.href} onClick={linkTo(item.href)} className={`${btnGhost} shrink-0`}>
                  {item.cta}
                </a>
              </li>
            ))}
          </ol>
        </div>
      )}

      {phase === 'ready' && recentMixes.length > 0 && (
        <div className={`border rounded-lg p-5 ${card}`}>
          <div className="flex items-center justify-between gap-2 mb-3">
            <h3 className={`text-xs font-bold uppercase tracking-widest ${muted}`}>Recent sets</h3>
            <a href={LIBRARY_ROUTE} onClick={linkTo(LIBRARY_ROUTE)} className="text-xs font-bold text-[#ea580c] hover:underline min-h-[44px] inline-flex items-center">
              View all
            </a>
          </div>
          <ul className="space-y-2" data-testid="dashboard-recent">
            {recentMixes.map((mix) => (
              <li key={mix.id} className={`p-3 rounded border ${row}`}>
                <a
                  href={libraryPath(mix.id)}
                  onClick={linkTo(libraryPath(mix.id))}
                  className={`block min-h-[44px] font-semibold text-sm ${isDark ? 'text-white' : 'text-gray-900'} hover:text-[#ea580c]`}
                >
                  {mix.title || mix.original_filename}
                </a>
                <p className={`text-[11px] font-mono mt-0.5 ${muted}`}>
                  {formatTime(mix.duration_seconds || 0)}
                  {mix.bpm ? ` · ${mix.bpm.toFixed(1)} BPM` : ' · Pending analysis'}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {phase === 'ready' && (failedJobs.length > 0 || unreadNotifications.length > 0) && (
        <div className={`border rounded-lg p-5 ${card}`}>
          <h3 className={`text-xs font-bold uppercase tracking-widest mb-3 ${muted}`}>
            Needs attention ({attentionCount})
          </h3>
          <ul className="space-y-2" data-testid="dashboard-attention">
            {failedJobs.map((job) => (
              <li key={job.id} className={`p-3 rounded border ${row}`} data-testid="dashboard-failed-row">
                <span className="flex flex-wrap items-center gap-2">
                  <a
                    href={jobDetailPath(job.id)}
                    onClick={linkTo(jobDetailPath(job.id))}
                    className="font-mono font-bold text-sm text-[#ea580c] hover:underline min-h-[44px] inline-flex items-center"
                  >
                    {job.job_type} failed
                  </a>
                  <StatusBadge status={job.status} isDark={isDark} />
                </span>
                <span className={`block text-[11px] font-mono mt-1 ${muted}`}>
                  {job.mixLabel}
                  {job.error_message ? ` · ${job.error_message}` : ''}
                </span>
              </li>
            ))}
            {unreadNotifications.slice(0, 5).map((item) => (
              <li key={item.id} className={`p-3 rounded border ${row}`}>
                <span className={`block text-xs font-bold font-mono ${isDark ? 'text-white' : 'text-gray-900'}`}>
                  {item.kind}
                </span>
                <a
                  href={safeNotificationLink(item.deep_link)}
                  onClick={linkTo(safeNotificationLink(item.deep_link))}
                  className="mt-1 inline-flex items-center min-h-[44px] text-xs font-bold text-[#ea580c] hover:underline"
                >
                  Open linked view
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {phase === 'ready' && mixesTotal > 0 && failedJobs.length === 0 && unreadNotifications.length === 0 && (
        <div className={`border rounded-lg p-5 ${card}`}>
          <EmptyState
            title="All clear."
            description="No failed jobs and no unread notifications."
          />
        </div>
      )}
    </div>
  );
};

export default DashboardPage;

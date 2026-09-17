import React from 'react';
import { BATCHES_ROUTE, JOBS_ROUTE, PROCESS_ROUTE, navigate, useSearchString } from '../../app/routes';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LiveRegion } from '../../components/ui/LiveRegion';
import { Skeleton } from '../../components/ui/Skeleton';
import { PushSettings } from './PushSettings';
import { useNotifications } from './useNotifications';
import { safeNotificationLink } from './notificationLinks';

interface NotificationCenterPageProps {
  isDark?: boolean;
}

/**
 * Durable notification center (PWA plan Task 3 frontend).
 * Renders authoritative GET /notifications state; read/dismiss persist
 * across reloads. Foreground job events surface as an accessible toast that
 * links to the center item — never as an OS notification.
 */
export const NotificationCenterPage: React.FC<NotificationCenterPageProps> = ({
  isDark = true,
}) => {
  const {
    items,
    unreadCount,
    phase,
    error,
    liveMessage,
    toast,
    refresh,
    markRead,
    dismiss,
    actionPending,
    actionError,
  } = useNotifications();
  const search = useSearchString();
  const fromPush = (() => {
    try {
      return new URLSearchParams(search).get('fromPush');
    } catch {
      return null;
    }
  })();
  const fromPushSafe = fromPush ? safeNotificationLink(fromPush) : null;
  const showFromPushBanner = fromPush !== null && fromPushSafe !== '/more/notifications';

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const row = isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]';
  const btnPrimary =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded shadow-sm disabled:opacity-50';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded disabled:opacity-50 no-underline'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded disabled:opacity-50 no-underline';

  const linkTo = (path: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };

  return (
    <div className="space-y-6" data-testid="notifications-view">
      <LiveRegion message={liveMessage} />
      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide">
            Notifications
          </h2>
          <span
            data-testid="notifications-unread-count"
            aria-label={`${unreadCount} unread notifications`}
            className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#ea580c]/20 text-[#ea580c] border border-[#ea580c]/30"
          >
            {unreadCount === 0 ? 'No unread' : `${unreadCount} unread`}
          </span>
        </div>
        <p className={`text-sm leading-relaxed mt-1 ${muted}`}>
          Durable job outcomes. Read and dismissed states persist across reloads.
        </p>
        <div className="flex flex-wrap gap-2 mt-4">
          <a href={JOBS_ROUTE} onClick={linkTo(JOBS_ROUTE)} className={btnGhost}>
            Back to Jobs
          </a>
          <a href={BATCHES_ROUTE} onClick={linkTo(BATCHES_ROUTE)} className={btnGhost}>
            Back to Batches
          </a>
          <a href={PROCESS_ROUTE} onClick={linkTo(PROCESS_ROUTE)} className={btnGhost}>
            Go to Pipeline
          </a>
        </div>

        {showFromPushBanner && fromPushSafe && (
          <p className={`text-xs mt-3 ${muted}`} data-testid="push-deep-link">
            Opened from a job alert:{' '}
            <a
              href={fromPushSafe}
              onClick={linkTo(fromPushSafe)}
              className="text-[#ea580c] hover:underline font-semibold min-h-[44px] inline-flex items-center"
            >
              Open linked view
            </a>
          </p>
        )}

        {toast && phase === 'ready' && (
          <div
            role="status"
            data-testid="notification-toast"
            className={`mt-4 p-3 rounded border ${row}`}
          >
            <p className={`text-xs ${isDark ? 'text-white' : 'text-gray-900'}`}>
              New job update: <span className="font-semibold">{toast.kind}</span>
            </p>
            <a
              href={safeNotificationLink(toast.deep_link)}
              onClick={linkTo(safeNotificationLink(toast.deep_link))}
              className="mt-1 inline-flex items-center min-h-[44px] text-xs font-bold text-[#ea580c] hover:underline"
            >
              View notification {toast.id.slice(0, 8)}
            </a>
          </div>
        )}

        <div className="mt-4">
          {phase === 'loading' && <Skeleton lines={3} label="Loading notifications" isDark={isDark} />}
          {phase === 'error' && items.length === 0 && (
            <ErrorState
              title="Could not load notifications"
              message={error ?? 'Notifications could not be loaded.'}
              onRetry={refresh}
              retryLabel="Retry"
              isDark={isDark}
            />
          )}
          {phase !== 'loading' && !(phase === 'error' && items.length === 0) && items.length === 0 && (
            <EmptyState
              title="No notifications yet."
              description="Completed or failed jobs will leave a durable item here."
            />
          )}
          {items.length > 0 && (
            <ul className="space-y-2" data-testid="notifications-list" aria-label="Notifications">
              {items.map((item) => {
                const read = Boolean(item.read_at) || (item.status || '').toLowerCase() !== 'unread';
                const dismissed = (item.status || '').toLowerCase() === 'dismissed';
                const safeLink = safeNotificationLink(item.deep_link);
                return (
                  <li
                    key={item.id}
                    data-testid="notification-item"
                    data-notification-id={item.id}
                    className={`p-3 rounded border ${row}`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`text-xs font-bold font-mono ${isDark ? 'text-white' : 'text-gray-900'}`}>
                        {item.kind}
                      </span>
                      <span
                        data-testid={`notification-status-${item.id}`}
                        className={`text-[11px] font-mono px-1.5 py-0.5 rounded border ${
                          dismissed
                            ? 'bg-neutral-500/15 text-neutral-400 border-neutral-500/40'
                            : read
                              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40'
                              : 'bg-amber-500/15 text-amber-400 border-amber-500/40'
                        }`}
                      >
                        {dismissed ? 'Dismissed' : read ? 'Read' : 'Unread'}
                      </span>
                    </div>
                    <p className={`text-[11px] font-mono mt-1 ${muted}`}>
                      {new Date(item.created_at).toLocaleString()} · job {item.job_id ?? '—'}
                    </p>
                    <div className="flex flex-wrap gap-2 mt-2">
                      <a
                        href={safeLink}
                        onClick={linkTo(safeLink)}
                        className="inline-flex items-center min-h-[44px] text-xs font-bold text-[#ea580c] hover:underline"
                      >
                        Open linked view
                      </a>
                      {!read && !dismissed && (
                        <button
                          type="button"
                          onClick={() => void markRead(item.id)}
                          disabled={actionPending === item.id}
                          className={btnPrimary}
                        >
                          {actionPending === item.id ? 'Marking…' : 'Mark as read'}
                        </button>
                      )}
                      {!dismissed && (
                        <button
                          type="button"
                          onClick={() => void dismiss(item.id)}
                          disabled={actionPending === item.id}
                          className={btnGhost}
                          aria-label={`Dismiss notification ${item.id}`}
                        >
                          {actionPending === item.id ? 'Dismissing…' : 'Dismiss'}
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          {actionError && (
            <p className="text-xs text-red-400 mt-2" role="alert">
              {actionError}
            </p>
          )}
        </div>
      </div>

      <PushSettings isDark={isDark} />
    </div>
  );
};

export default NotificationCenterPage;

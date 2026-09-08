import { Link } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { ErrorState } from "../../components/ui/ErrorState";
import { useNotifications } from "./useNotifications";

export function NotificationCenterPage() {
  const { items, total, loading, problem, mutationError, pendingIds, retry, markRead, dismiss } = useNotifications();

  return (
    <section className="route-page" aria-labelledby="page-heading">
      <p className="eyebrow">More / Notifications</p>
      <h1 id="page-heading" tabIndex={-1}>Notifications</h1>
      <p className="route-page__description">Job results stay here until you dismiss them. Read and dismiss state is stored by the service, not just this browser tab.</p>

      {problem ? <ErrorState onRetry={retry} problem={problem} /> : null}
      {loading && items.length === 0 && !problem ? <section className="resource-state" aria-live="polite"><h2>Loading notifications</h2><p>Checking your durable job results.</p></section> : null}
      {!loading && !problem && items.length === 0 ? <section className="resource-state"><h2>No notifications yet</h2><p>Completed or failed jobs will appear here when there is something you need to review.</p></section> : null}

      {items.length > 0 ? (
        <>
          <p className="jobs-page__count">Showing <strong>{items.length}</strong> of {total} active notification{total === 1 ? "" : "s"}.</p>
          <ol className="jobs-list" aria-label="Notifications">
            {items.map((notification) => {
              const pending = pendingIds.has(notification.id);
              const unread = notification.read_at === null;
              return (
                <li className="job-card" key={notification.id}>
                  <div className="job-card__summary">
                    <div>
                      <p className="job-card__eyebrow">{notification.kind.replace(/\./g, " · ")}</p>
                      <h2>{notification.title}</h2>
                    </div>
                    <span className={`status-badge ${unread ? "status-badge--running" : "status-badge--succeeded"}`}>{unread ? "Unread" : "Read"}</span>
                  </div>
                  {notification.body ? <p>{notification.body}</p> : null}
                  <time className="job-card__time" dateTime={notification.created_at}>{new Date(notification.created_at).toLocaleString()}</time>
                  <div className="job-detail-page__actions">
                    <Link className="button button--secondary" to={notification.deep_link}>Open job</Link>
                    {unread ? <Button disabled={pending} onClick={() => void markRead(notification.id)} tone="secondary">Mark as read</Button> : null}
                    <Button disabled={pending} onClick={() => void dismiss(notification.id)} tone="quiet">Dismiss</Button>
                  </div>
                </li>
              );
            })}
          </ol>
        </>
      ) : null}

      {mutationError ? <p className="process-form__problem" role="alert"><strong>Could not update notification.</strong> {mutationError}</p> : null}
    </section>
  );
}

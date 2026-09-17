/** Safe same-origin deep links for notification payloads (PWA plan Task 5). */

export const NOTIFICATION_CENTER_PATH = '/more/notifications';

/**
 * True only for the allow-listed same-origin routes a notification may open:
 * /jobs/:id, /batches/:id, /more/notifications, /pipeline, /.
 * Everything else falls back to the notification center.
 */
export function isSafeNotificationPath(path: unknown): path is string {
  if (typeof path !== 'string') return false;
  if (!path.startsWith('/') || path.startsWith('//')) return false;
  if (path.includes(' ') || path.includes('\\')) return false;
  const clean = path.split('#')[0].split('?')[0];
  if (clean === '/' || clean === '/pipeline' || clean === NOTIFICATION_CENTER_PATH) {
    return true;
  }
  const jobsPrefix = '/jobs/';
  if (clean.startsWith(jobsPrefix)) {
    const rest = clean.slice(jobsPrefix.length);
    return rest.length > 0 && !rest.includes('/');
  }
  const batchesPrefix = '/batches/';
  if (clean.startsWith(batchesPrefix)) {
    const rest = clean.slice(batchesPrefix.length);
    return rest.length > 0 && !rest.includes('/');
  }
  return false;
}

/** Resolve a stored deep link to a safe path, falling back to the center. */
export function safeNotificationLink(deepLink: string | null | undefined): string {
  if (typeof deepLink === 'string' && isSafeNotificationPath(deepLink)) {
    return deepLink.split('#')[0].split('?')[0];
  }
  return NOTIFICATION_CENTER_PATH;
}

export default isSafeNotificationPath;

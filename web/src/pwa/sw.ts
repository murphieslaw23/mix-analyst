/// <reference lib="webworker" />
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { safeNotificationLink } from '../features/notifications/notificationLinks';

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

// Versioned precache (injected at build time).
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// App-shell fallback for navigations only. Operational traffic stays
// network-only: no cached API response may ever impersonate the backend.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('/index.html'), {
    denylist: [/^\/api\//, /^\/uploads\//, /^\/downloads\//],
  }),
);

const CENTER_PATH = '/more/notifications';

interface PushPayload {
  version?: number;
  notification_id?: string;
  deep_link?: string;
}

function readPayload(event: PushEvent): PushPayload {
  try {
    const data = event.data?.json() as PushPayload | null;
    if (data && typeof data === 'object') return data;
  } catch {
    // Non-JSON push: fall back to the center link below.
  }
  return {};
}

self.addEventListener('push', (event: PushEvent) => {
  const payload = readPayload(event);
  const target = safeNotificationLink(payload.deep_link ?? null);
  const title = 'SYCO23 Mix';
  // The payload carries no filename, error text, or credential — the body
  // stays generic by design; details live behind the authorized route.
  const options: NotificationOptions & { data?: { deep_link: string } } = {
    body: 'Your audio job finished — open to view results.',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    tag: payload.notification_id ?? 'syco23-job',
    data: { deep_link: target },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close();
  const raw = (event.notification.data as { deep_link?: unknown } | null)?.deep_link;
  const target =
    typeof raw === 'string' ? safeNotificationLink(raw) : CENTER_PATH;
  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((existing) => {
        for (const client of existing) {
          const url = new URL((client as WindowClient).url);
          if (url.pathname === target) return (client as WindowClient).focus();
        }
        for (const client of existing) {
          if ('navigate' in client) {
            return (client as WindowClient)
              .navigate(target)
              .then((navigated) => navigated?.focus());
          }
        }
        return self.clients.openWindow(target);
      }),
  );
});

self.addEventListener('notificationclose', () => {
  // Dismissal needs no bookkeeping: read state lives server-side.
});

self.addEventListener('pushsubscriptionchange', (event: ExtendableEvent) => {
  // Re-enrollment needs the VAPID key + user gesture, which only the page
  // has: ask a controlled client to run the opt-in flow again.
  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((existing) =>
        Promise.all(
          existing.map((client) =>
            (client as WindowClient).postMessage({ type: 'PUSH_RESUBSCRIBE' }),
          ),
        ),
      )
      .then(() => undefined),
  );
});

import { matchPrecache, precacheAndRoute } from "workbox-precaching";

// Vite PWA injects revisioned build assets here. This is deliberately not a
// general runtime cache: private audio and every operational request remains
// network-only.
precacheAndRoute(self.__WB_MANIFEST);

const appShell = "/index.html";

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET" || request.mode !== "navigate") return;

  const pathname = new URL(request.url).pathname;
  // A failed operation endpoint must never be presented as a successful app
  // document. Downloads and future media endpoints likewise stay network-only.
  if (/^\/(?:api|downloads|uploads|audio|subscriptions|preferences)(?:\/|$)/.test(pathname)) return;

  event.respondWith(
    fetch(request).catch(async () => (await matchPrecache(appShell)) ?? Response.error()),
  );
});

// Prompt-mode registration sends this only after the person selected Update
// now. No install/activate handler calls skipWaiting automatically.
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

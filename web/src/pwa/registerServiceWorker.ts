import { registerSW } from "virtual:pwa-register";

export interface ServiceWorkerCallbacks {
  onNeedRefresh: () => void;
  onOfflineReady: () => void;
}

/**
 * Register the generated worker once the app has rendered. The returned action
 * is intentionally the only route that can send SKIP_WAITING to a waiting
 * worker; callers present their own explicit user decision before invoking it.
 */
export function registerServiceWorker({ onNeedRefresh, onOfflineReady }: ServiceWorkerCallbacks): () => Promise<void> {
  if (!import.meta.env.PROD) return async () => undefined;

  return registerSW({
    immediate: true,
    onNeedRefresh,
    onOfflineReady,
    // A failed registration must not make the audio-processing application
    // unusable. The normal network application remains available.
    onRegisterError: () => undefined,
  });
}
